# HiVideo 项目 · 完整目录结构分析报告

## 📋 执行摘要

**项目路径**：`/Users/hikari/Documents/Git/HiVideo/`  
**项目类型**：文档驱动设计（Design-First）  
**当前阶段**：PRD + 设计阶段（代码未开始）  
**总体积**：~400KB（纯文档 + 配置，无源代码）

---

## 🗂️ 目录树（完整 3 层）

```
HiVideo/
│
├── README.md                                    ← 项目总览入口（12.4KB）
│
├── docs/                                        ← 文档库
│   ├── PRD.md                                   ← HiVideo PRD v0.8（~12.4KB）
│   ├── dev-plan/
│   │   └── DEV-PLAN.md                          ← 开发计划（11 Phase, 49 周）
│   └── companion/
│       └── HiPixel-PRD.md                       ← HiPixel PRD v0.2（Web+Server）
│
├── .claude/
│   └── settings.local.json                      ← Claude Code 本地配置
│
├── .workbuddy/
│   └── memory/
│       └── 2026-05-30.md                        ← 工作日志与决策记录
│
├── .git/                                         ← Git 版本控制
│   ├── config
│   ├── objects/
│   ├── refs/
│   └── hooks/
│
├── .gitignore                                   ← Git 忽略规则
│
└── .DS_Store                                    ← macOS 系统文件
```

---

## 📄 核心文档详解

### 1️⃣ **README.md** — 项目总览（12.4KB）

**内容结构**：
- 文档地图：PRD/HiPixel-PRD/开发计划/日志导航
- 一句话定位
- 8 条设计哲学
- HiVideo 功能全景（9 大模块）
- HiPixel 全景
- HiVideo ↔ HiPixel 联动流程
- 全局技术栈速查表
- 16 个 AI 模型清单
- 双线路线图
- 6 个待决策问题

**关键数据**：
- HiVideo：26 周到 v1.0
- HiPixel：12 周后启动 Beta

---

### 2️⃣ **docs/PRD.md** — HiVideo 完整需求文档（v0.8）

**版本演变**：
- v0.1：初版基础
- v0.2：加快捷键 + 资源管理
- v0.3：升级角色识别系统
- v0.4：加网盘支持
- v0.5：加多副本合并 + 副本选择弹窗
- v0.6：加字幕子系统
- v0.7：加画质增强 + 智能音量
- v0.8：加 HiPixel 远程算力节点

**核心章节**（11 部分）：
1. 愿景与设计哲学
2. 用户画像与场景（7 大场景）
3. 功能模块总览
4. **详细规范**（最核心！）
   - §4.1 播放内核（P0）
     - 4.1.1 解码与渲染
     - 4.1.2 播放控制
     - 4.1.3 视觉与交互
     - **4.1.4 AI 实时画质增强**
       - 10 种滤镜（超分/降噪/HDR/插帧/上色/锐化等）
       - 智能预设系统
       - 性能保护机制
     - **4.1.5 智能音量与对话增强**
       - 响度归一化（EBU R128）
       - 对话增强（Demucs Lite）
       - 深夜模式（动态压限）
       - AirPods 空间音频
     - **4.1.6 HiPixel 远程算力节点**（新！）
       - 零配置发现（mDNS）
       - 任务路由策略
       - 文件传输（3 选 1）
       - 多节点池
   - §4.2 媒体库
   - §4.3 AI 智能层（角色识别 5 路融合）
   - §4.4 字幕子系统（三路来源 + 5 路对齐）
   - §4.5 快捷键系统（三层心智 + 100+ 快捷键）
   - §4.6 资源管理（永不真删）
   - §4.7 网盘与远程存储（P0 8 种 + P1 10 种 + P2 社区）
   - §4.8 扩展插件
   - §4.9 系统集成
5. 界面设计原则
6. 性能目标（8 个量化指标）
7. 技术架构概要
8. 开发路线图（5 Phase）
9. 开放性问题（4 大待决策）
10. 风险与对策
11. 成功指标

**关键数据**：
- 模型数：13 个主模型
- 快捷键：100+ 个
- 网盘支持：P0 8+P1 10 共 18 种
- 滤镜数：10 个实时增强滤镜

---

### 3️⃣ **docs/companion/HiPixel-PRD.md** — v0.2

**姊妹产品定位**：
- HiVideo：看（实时观看时增强）
- HiPixel：出（离线批量增强并导出文件）

**核心差异**：
| 维度 | HiVideo | HiPixel |
|------|---------|---------|
| 形态 | macOS 桌面播放器 | Web 前端 + Server 后端 |
| 场景 | 实时观看 | 离线批处理 |
| 输出 | 屏幕渲染 | mp4/mkv 文件 |
| 用户 | 普通看片 | 创作者/影视修复 |

**部署形态**（v0.2 新增）：
1. **Windows 一键安装包**（主推）
   - HiPixel-Setup.exe
   - 自动 GPU 检测
   - 系统托盘 + mDNS 广播
   - < 200MB（模型按需下载）
2. macOS dmg 包
3. Docker Compose（NAS/Linux）
4. Kubernetes 集群
5. 托管云服务

**GPU 后端矩阵**：
- NVIDIA RTX 30/40/50 → TensorRT FP16 → **3-8× 实时**
- AMD RX 6/7000 → DirectML → 0.5-2× 实时
- Intel Arc → OpenVINO → 0.5-1× 实时
- Apple Silicon → CoreML/MPS → 1-3× 实时

**6 大预设**：
1. 老片救星
2. 番剧增强
3. 黑白复刻
4. HDR 兼容
5. 丝滑插帧 60fps
6. 极致修复

---

### 4️⃣ **docs/dev-plan/DEV-PLAN.md** — 开发计划

**整体规划**：
- 11 个 Phase
- 49 周总周期
- 9 个关键里程碑（M1-M9）
- 6 个待决策问题

**Phase 分解**：

| Phase | 名称 | 周数 | 状态 | 完成度 |
|-------|------|------|------|--------|
| 0 | hipixel-core 内核抽离 | 3 | ⏸ | 0% |
| 0.5 | UI/UX 设计与原型 | 3 | ⏸ | 0% |
| 1 | HiVideo MVP 播放器 | 6 | ⏸ | 0% |
| 2 | HiPixel MVP Web | 5 | ⏸ | 0% |
| 3 | HiVideo AI 入场 | 6 | ⏸ | 0% |
| 4 | HiPixel 分布式+Windows | 4 | ⏸ | 0% |
| 5 | 智能管家（角色/摘要/跳过） | 4 | ⏸ | 0% |
| 6 | 字幕子系统 | 3 | ⏸ | 0% |
| 7 | 网盘+副本管理 | 4 | ⏸ | 0% |
| 8 | 远程节点联动 | 3 | ⏸ | 0% |
| 9 | 扩展插件+系统集成 | 4 | ⏸ | 0% |
| 10 | 打磨+上线 | 4 | ⏸ | 0% |

**Phase 0 · hipixel-core 内核抽离（3 周）**：
- 0.1 项目骨架（Cargo workspace）
- 0.2 GPU 后端抽象（CoreML/CUDA/DirectML/OpenVINO）
- 0.3 视频解编码
- 0.4 第一个滤镜（Real-ESRGAN）
- 0.5 滤镜流水线
- 0.6 预设系统
- 0.7 CLI 命令实现
- 0.8 验证与基准测试
- 0.9 打包与发布

**Phase 0.5 · UI/UX 设计（3 周）**（新增！）：
- 0.5.1 设计基础设施（Figma）
- 0.5.2 设计 Token + 组件库
- 0.5.3 HiVideo 核心界面设计
  - 启动屏 / 媒体库 / 播放器 / 命令面板 / 角色识别

---

### 5️⃣ **工作日志** — 2026-05-30.md

**决策记录**：
- 风格：极致简洁派
- 起步：PRD 文档先行
- AI 部署：本地优先
- 硬件：仅 Apple Silicon
- 设计工具：Figma

**版本演变标记**：
- v0.1 → v0.8 的 8 个版本增补
- 每个版本对应的功能追加和设计决策

**已完成交付物**：
- ✅ PRD v0.8
- ✅ HiPixel PRD v0.2
- ✅ UI 高保真原型（2 张：角色侧边栏 + 角色详情页）
- ✅ DEV-PLAN.md
- ✅ README.md

---

## 🔍 关键发现

### 1. 📌 **没有现成的 hipixel-core 代码**
- 完全是文档阶段
- 推荐先启动 Phase 0 创建内核骨架

### 2. 🎯 **超完整的产品规划**
- **9 大功能模块**：播放 / 媒体库 / AI / 字幕 / 快捷键 / 资源管理 / 网盘 / 插件 / 系统集成
- **16 个 AI 模型**：覆盖嵌入 / 检测 / 增强 / 音频等全链路
- **100+ 快捷键**：三层心智模型
- **18 种网盘支持**：P0 首发 8 + P1 计划 10

### 3. 🏗️ **分层递进的设计**
- Phase 0.5 强制设计走查
- 每个 Phase 包含"设计先行 → 评审 → 编码"子流程
- 避免代码返工

### 4. 🔐 **隐私与安全作为 P0**
- 所有 AI 任务本地优先
- 网盘凭据走 macOS Keychain
- 用户完全可控远程与本地的切换

### 5. 🎮 **创新的副本与网盘管理**
- MediaItem（逻辑视频）vs Variant（物理副本）
- 智能副本合并（多信号融合）
- 网盘能力矩阵（13 种协议 × 5 种操作）
- 网盘禁移五道防线

### 6. 🌐 **HiVideo ↔ HiPixel 双向联动**
- 共享 hipixel-core 内核
- HiVideo 可右键发送到 HiPixel
- HiPixel 处理完回传新 Variant
- mDNS 零配置发现

### 7. 💻 **跨平台一致性设计**
- macOS 应用专业力
- Windows HiPixel Server 一等公民
- ONNX 统一模型格式
- 性能基准跨平台对标

---

## 🚀 技术栈一览

### 前端 / UI
- **macOS**：SwiftUI + AppKit（必要时混合）
- **Web**：React + Vite + shadcn/ui + Zustand
- **渲染**：Metal + VideoToolbox + ColorSync

### AI / 推理
- **macOS**：Core ML + ONNX Runtime（ANE / Metal）
- **跨平台**：ONNX Runtime
- **Windows**：TensorRT / CUDA / DirectML / OpenVINO
- **共享核心**：Rust 内核 + Python 胶水（hipixel-core）

### 数据 / 存储
- **本地**：SQLite + sqlite-vec（向量嵌入）
- **服务端**：PostgreSQL
- **对象存储**：S3 / MinIO

### 后端 / 服务
- **API**：FastAPI（Python）
- **任务队列**：Redis Stream / RabbitMQ
- **编解码**：FFmpeg（跨平台）+ VideoToolbox（macOS） / NVDEC（NVIDIA）

### 插件系统
- **JavaScript**：JavaScriptCore + Swift 沙箱
- **Swift**：沙箱二进制

---

## 📊 当前状态

| 交付物 | 状态 | 完成度 |
|--------|------|--------|
| **HiVideo PRD** | ✅ v0.8 完成 | 100% |
| **HiPixel PRD** | ✅ v0.2 完成 | 100% |
| **UI 高保真原型** | 🟡 部分 | 30%（已完成角色相关2屏） |
| **开发计划** | ✅ DEV-PLAN.md | 100%（计划） |
| **Xcode 项目骨架** | ⏸ 未开始 | 0% |
| **hipixel-core** | ⏸ 未开始 | 0% |

---

## 📝 所有关键问题（6 大待决策）

1. **HiVideo 分发渠道**
   - Mac App Store？还是直接 dmg？
   - 影响：插件审核与 Whisper 模型大小

2. **付费模式**
   - 买断 / 订阅 / 免费 + AI 增强订阅 / 完全开源

3. **iOS / iPadOS 配套**
   - Catalyst 还是原生 iOS？

4. **HiPixel 商业化**
   - 推荐"开源核心 + 托管 SaaS"
   - 自部署免费扩散，SaaS 按 GPU 分钟计费

5. **插件市场审核**
   - 早期人工审核 vs 社区开放

6. **品牌系列化**
   - 未来是否扩展 HiAudio / HiSub 等

---

## 🎯 下一步推荐（按优先级）

### 最高优先级：**Phase 0 · hipixel-core 内核抽离**
**目标**：跑通 `hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4`

**第 1 周（Day 1-7）**：
- [ ] 创建 monorepo（Cargo + Python pyproject）
- [ ] 配置 CI（macOS + Linux + Windows 矩阵）
- [ ] 定义 GPU 后端抽象层
- [ ] 实现 CoreML 后端
- [ ] FFmpeg 解码封装

**第 2-3 周**：
- [ ] Real-ESRGAN 超分滤镜
- [ ] 其他滤镜（Anime4K / NAFNet 等）
- [ ] 预设系统
- [ ] CLI 命令
- [ ] 性能基准测试

### 次高优先级：**Phase 0.5 · UI/UX 设计冻结**
- 在 Phase 0 同步进行（设计师 vs 工程师分工）
- 完成所有核心界面的高保真设计稿
- 导出 Figma Token + 切图

### Phase 1 启动前置：**HiVideo Xcode 项目骨架**
- 一旦 hipixel-core 有可用 CLI
- 立即启动 Xcode 项目搭建
- 通过 Swift Bridge 调用 hipixel-core
- 验证 1080p H.264 实时播放

---

## 📂 文件清单（完整）

```
/Users/hikari/Documents/Git/HiVideo/
├── .claude/
│   └── settings.local.json                      ← Claude Code 配置
├── .workbuddy/
│   └── memory/
│       └── 2026-05-30.md                        ← 工作日志 (238 行)
├── .git/                                         ← Git 仓库
├── .gitignore                                   ← 忽略规则
├── .DS_Store                                    ← macOS 系统文件
├── README.md                                    ← 总览 (289 行, 12.4KB)
└── docs/
    ├── PRD.md                                   ← HiVideo PRD (1425 行)
    ├── dev-plan/
    │   └── DEV-PLAN.md                          ← 开发计划 (11 Phase)
    └── companion/
        └── HiPixel-PRD.md                       ← HiPixel PRD (150+ 行)
```

---

## 💡 使用建议

### 对新加入开发者
1. 先读 **README.md** 获得 30 分钟快速概览
2. 再读 **PRD.md** 的前 3 章理解设计哲学
3. 最后按章节深入 PRD 的自己负责模块

### 对项目经理
1. 使用 **DEV-PLAN.md** 的看板追踪进度
2. 每周检查"✅ / 🔄 / ⏸ / ⚠"状态变化
3. Phase 完成后立即标记下一个 Phase 的第一个 Day 为 🔄

### 对设计师
1. 参考 **0.5.3 E. 章节已有部分原型**
2. 在 Figma 中建立 Design Token 库
3. 逐个完成 9 大功能模块的设计稿

### 对工程师
1. 阅读 **Phase 0 · 内核抽离** 的完整任务列表
2. 建立 monorepo 后立即 commit + PR
3. 性能基准是 Go / No-Go 的关键指标

---

> **文档完成** ✅  
> 最后更新：2026-05-30  
> 项目状态：文档与设计阶段，代码即将启动

