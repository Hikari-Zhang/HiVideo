# HiVideo · 项目总览（README）

> 一个 macOS 极简 AI 原生视频播放器，加上一个独立的 Web + Server 画质增强服务，组成完整的家庭视频生态。

---

## 1. 文档地图

| 文档 | 路径 | 内容 |
|---|---|---|
| **HiVideo PRD** | `docs/PRD.md` | macOS 桌面播放器的完整产品需求文档（v0.8） |
| **HiPixel PRD** | `docs/companion/HiPixel-PRD.md` | 独立 Web + Server 画质增强服务（v0.2） |
| **🚀 开发计划** | `docs/dev-plan/DEV-PLAN.md` | 11 个 Phase 的任务清单与进度追踪 |
| **本文档** | `README.md` | 项目总览与快速导航 |
| 工作日志 | `.workbuddy/memory/2026-05-30.md` | 设计过程的关键决策与演进 |

---

## 2. 一句话定位

| 产品 | 定位 |
|---|---|
| **HiVideo** | 「打开就能用，看完就懂你」的 macOS 视频播放器 |
| **HiPixel** | 「上传 → 选预设 → 等待 → 下载」的 AI 视频画质增强服务 |
| **共享内核** | `hipixel-core` —— 模型 / 滤镜 / 预设 / 解码编码 / 跨 GPU 抽象 |

> **HiVideo 是「看」**（实时观看时增强）
> **HiPixel 是「出」**（离线批量出片）
> 两个产品共用一份 AI 内核，一处更新两端共享。

---

## 3. 核心设计哲学（贯穿所有功能）

| 哲学 | 体现 |
|---|---|
| **极致简洁派** | 参考 Apple TV App，零冗余零打扰 |
| **AI 是空气而非按钮** | 智能默默工作，用户感知是"它已经准备好了" |
| **原生即美** | SwiftUI / Metal / Core ML / ANE 深度集成 |
| **隐私优先** | 默认全本地，云端 / 远程是用户主动选择 |
| **永不真删** | 删除全走回收站 + 撤销 toast + 30 分钟内可恢复 |
| **本地与远程一视同仁** | NAS / 网盘 / iCloud 视频在媒体库等同于本地 |
| **逻辑视频 vs 物理副本** | MediaItem 是 UI 卡片，Variant 是物理文件 |
| **透明可控** | AI 算力实时仪表，每次远程发送都有提示 |

---

## 4. HiVideo 功能全景（v0.8）

### 4.1 播放内核（P0）
- 全格式硬解（H.264 / H.265 / AV1 / VP9 / ProRes）
- HDR / Dolby Vision Profile 5 & 8
- Metal 渲染，CPU < 8% 看 4K HDR
- 倍速不变调（0.25-4x）/ 帧步进 / A-B 循环
- **§4.1.4 AI 实时画质增强**：超分（Real-ESRGAN / Anime4K）、降噪、HDR↔SDR、插帧、上色、锐化，10 种滤镜按需启用 + 6 个智能预设
- **§4.1.5 智能音量与对话增强**：响度归一化（EBU R128 全库 -23 LUFS）、Demucs Lite 对话增强、深夜模式、AirPods 空间音频
- **§4.1.6 HiPixel 远程算力节点**：mDNS 零配置发现、mTLS 配对、本地 + 远程任务路由、多节点池

### 4.2 媒体库（P0）
- 智能扫描 + 元数据抓取
- AI 分类（按内容类型 / 场景 / 人物 / 时间 / 续播状态）
- 网格 / 列表 / 时间线视图

### 4.3 AI 智能层（P0 · 核心差异化）
- 自动分类（CLIP 嵌入 + HDBSCAN 聚类）
- 自然语言搜索（"海边日落的镜头"直接定位）
- 智能字幕（详见 §4.4）
- 视频摘要（关键帧 + LLM）
- 智能跳过片头片尾
- **角色识别**：5 路多模态融合（真人脸 0.40 + 动漫脸 0.40 + 全身 ReID 0.20 + 声纹 0.25 + 字幕 0.15）→ 命名三层来源（TMDB / 字幕推断 / 用户手动）→ 角色筛选 / 对手戏 / 高光集锦 / 台词搜索

### 4.4 字幕子系统（P0）
- 三路来源：在线下载（OpenSubtitles / 射手 / Assrt 等）/ Whisper 本地 / 用户上传
- **AI 辅助对齐五路管线**：Whisper 锚点 + DTW（0.55）/ 静默检测（0.20）/ 互相关（0.15）/ LLM 段落映射（0.10）/ 手动锚点
- 精度目标：同帧率 ±50ms / 帧率差 ±200ms / 不同剪辑版本 ±500ms
- 字幕编辑器：三栏（列表 / 预览 / 波形）+ AI 修订
- 双语 + 词典悬停 + ASS 高级样式 + 5 种风格预设

### 4.5 快捷键系统（P0 · 操作简单的灵魂）
- 三层心智：基础 8 键 / 进阶 ⌘ 修饰 / 专家 Vim 模式
- ⌘K 命令面板（万能入口）
- ⌘/ 速查面板
- 预设方案：默认 / Vim / IINA / VLC / mpv 一键切换
- 录制式自定义快捷键

### 4.6 资源管理系统（P0）
- 永不真删（⌘⌫ 回收站 + 5s 撤销 toast + 30 分钟内可恢复）
- ⌘⇧⌫ 永久删除二次确认
- Finder 集成（⌘R / ⌘⇧R / ⌘⌥C / ⌘⌥M）
- 批量操作面板
- **多副本合并（Variant Grouping）**：内容指纹 + 帧 pHash + 音频指纹 + 时长 + 文件名加权融合 → 自动合并 / 候选 / 不合并
- **副本选择弹窗**：作用于物理文件的操作必弹窗，UI 自动适配能力
- 重复文件检测 / 磁盘空间面板 / 文件完整性

### 4.7 网盘与远程存储（P0）
- **三梯队分级**：
  - P0 首发：SMB / WebDAV / NFS / AFP / DLNA / Jellyfin / Plex / Emby
  - P1 1-2 月：iCloud / Google / OneDrive / Dropbox / 阿里云盘 / 百度 / 115 / S3 / SFTP
  - P2 插件：迅雷 / 夸克 / 123（社区维护）
- **流播策略**：直接流式 + Range / 智能预取 60s / 离线缓存 LRU / 服务端转码协商
- **AI 远程友好**：扫描只读头部、抽 20 关键帧、Whisper 仅拉音轨（视频 5%）
- **网盘禁移五道防线**：UI 灰显 / 快捷键拦截 / Finder 拖拽拦截 / 批量自动跳过 / 隐藏管理员模式
- 网盘诊断面板：连通性 / 带宽 / Range 支持

### 4.8 扩展插件（P1）
- JS + Swift 双语沙箱
- 首发：TMDB / Bangumi / 弹幕 / Trakt / Subtitles.org

### 4.9 系统集成（P1）
- Spotlight / 服务菜单 / 触控栏 / 通知中心 / 快捷指令 / iCloud / AirPlay

---

## 5. HiPixel 功能全景（v0.2）

### 三种部署形态
| 形态 | 适用 |
|---|---|
| **Windows 一键安装包** | 家用 RTX 工作站 / 闲置 PC 复用 |
| **macOS 应用包** | Mac mini 当家庭 GPU 节点 |
| **Docker Compose** | NAS / Linux 服务器 |
| **Kubernetes 集群** | 工作室 / 团队 |
| **托管 SaaS** | 偶发用户 |

### 核心功能
- **上传**：拖拽 / URL / API / 远程拉取（NAS/S3 直连免上传）
- **6 张预设大卡**：老片救星 / 番剧增强 / 黑白复刻 / HDR 兼容 / 丝滑插帧 / 极致修复 / 最快速度
- **任务队列**：进度颗粒度到帧 + 阶段 + ETA
- **before/after 对比**：拖动分割线左右对比 + 关键帧报告
- **结果交付**：浏览器下载 / 短链分享 / 推送网盘 / API 拉取

### 异构 GPU（一份代码三类卡）
| 显卡 | 后端 | 1080p Real-ESRGAN |
|---|---|---|
| RTX 30/40/50 | TensorRT FP16 | 3-8× 实时 |
| GTX | CUDA FP32 | 0.4-0.8× 实时 |
| AMD RX 6/7000 | DirectML | 0.5-2× 实时 |
| Intel Arc | OpenVINO | 0.5-1× 实时 |
| Apple Silicon | CoreML / MPS | 1-3× 实时 |

### Windows 平台一等公民（§4.11）
- 一键 exe 安装包（< 200MB，模型按需下载）
- 自动检测 GPU 拉对应推理后端
- 系统托盘图标 + mDNS 广播
- NVENC / AMF / Quick Sync 硬编码加成
- DirectStorage 大文件直读
- EV Code Signing 避免 SmartScreen 警告

### 跨平台一致性
- 同一 ONNX → TRT / DML / OpenVINO 转换
- CI 跑 ubuntu + windows 双平台
- 一致性测试：PSNR / SSIM 差 ≤ 0.5dB

---

## 6. HiVideo ↔ HiPixel 联动

```
家里：Windows 工作站（RTX 4090）跑 HiPixel Server
        ↓ 局域网 mDNS 广播
办公：MacBook 上的 HiVideo 自动发现「家里-RTX4090」
        ↓ 用户右键视频 →「发送到家里的 GPU」
        ↓ 方案 3：节点直拉 NAS 源文件（双方都已配凭据）
HiPixel 在家里跑 Anime4K 增强（5× 实时）
        ↓ 完成后写回 NAS / 直推 MacBook
HiVideo 媒体库出现新 Variant
        ✨ AI 修复 · 来源：家里-RTX4090 · 处理时间 5min
        ↓ 下次播放自动选最高画质副本
```

| 联动维度 | 实现 |
|---|---|
| 服务发现 | mDNS `_hipixel._tcp.local` 局域网零配置 |
| 配对 | 一次性配对码 + DH 密钥交换 |
| 信任 | 双向 mTLS，凭据存 macOS Keychain |
| 公网 | WireGuard / Tailscale 双层加密 |
| 文件 | 共享网盘传递（推荐） / 节点直拉源 / 直接上传 |
| 结果 | 输出作为新 Variant 加入原 MediaItem |
| UI 标识 | ✨ AI 修复徽章 + 来源节点名称 + 处理时间 |
| 撤销 | 一键吊销节点信任 + 30 天审计日志 |

---

## 7. 全局技术栈

| 层 | 选型 |
|---|---|
| **macOS UI** | SwiftUI + AppKit（必要时混合） |
| **macOS 渲染** | Metal + VideoToolbox + ColorSync |
| **macOS 解码** | FFmpeg + VideoToolbox 硬解 |
| **macOS 推理** | Core ML + ONNX Runtime（ANE / Metal） |
| **macOS 数据** | SQLite + sqlite-vec |
| **macOS 插件** | JavaScriptCore + Swift 沙箱 |
| **Web 前端** | React + Vite + shadcn/ui + Zustand |
| **Server API** | FastAPI + Redis Stream + PostgreSQL |
| **对象存储** | MinIO / S3 兼容 |
| **Windows 推理** | TensorRT / CUDA / DirectML / OpenVINO |
| **跨平台共享** | hipixel-core（Rust + Python） |

---

## 8. AI 模型清单

| 模型 | 用途 | 大小 | 后端 |
|---|---|---|---|
| CLIP ViT-B/32 | 视频/帧嵌入 | 150 MB | ANE |
| YOLOv8-Seg | 物体识别 | 22 MB | ANE |
| RetinaFace + ArcFace | 真人人脸 | 107 MB | ANE |
| AnimeFace Detect+Recognizer | 动漫角色 | 80 MB | ANE |
| OSNet | 全身 ReID | 20 MB | ANE |
| pyannote-3.1 | 说话人分离 | 85 MB | Metal |
| Whisper Large v3 Turbo | 语音转写 | 1.5 GB | Metal |
| MiniLM (Sentence-BERT) | 文本嵌入 | 80 MB | ANE |
| 可选：Llama 3.2 3B / Qwen 2.5 3B | 摘要 / 自然语言 | 2 GB | Metal + ANE |
| Real-ESRGAN-General-x2 | 实拍超分 | 67 MB | ANE |
| Anime4K v4 / waifu2x | 动漫超分 | 30 MB | Metal |
| NAFNet / SCUNet | AI 降噪 | 120 MB | ANE |
| RIFE-v4.6 | 视频插帧 | 45 MB | ANE |
| iSDR2HDR | SDR→HDR | 28 MB | ANE |
| DeOldify-Lite | 黑白上色 | 95 MB | ANE |
| Demucs Lite | 人声分离 | 80 MB | ANE |

按需下载，可单独卸载。

---

## 9. 路线图（HiVideo + HiPixel 双线）

```
         Phase 0       Phase 1        Phase 2        Phase 3        Phase 4        Phase 5
HiVideo  基建 2w  →   MVP 6w     →  AI 入场 6w  → 智能管家 4w → 扩展生态 4w → 打磨上线 4w
                                                                              ↑ 1.0 正式
HiPixel  内核 3w  →   MVP Web 5w →  分布式 4w   → 闭环 4w     → 商业化 4w
                                                                              ↑ Beta 上线
```

**HiVideo 1.0**：26 周（约 6 个月）
**HiPixel Beta**：12 周后跟上（核心可用）
**HiPixel 1.0**：20 周（5 个月）

可并行：Phase 0 抽离内核同时开始 HiVideo Phase 0 基建。

---

## 10. 待决策的关键问题

1. **HiVideo 分发渠道**：Mac App Store？还是直接发 dmg？影响插件审核与 Whisper 模型大小
2. **付费模式**：买断 / 订阅 / 免费 + AI 增强订阅 / 完全开源
3. **iOS / iPadOS 配套**：Catalyst 还是原生 iOS？
4. **HiPixel 商业化**：推荐"开源核心 + 托管 SaaS"（自部署免费扩散，SaaS 按 GPU 分钟计费）
5. **插件市场审核**：早期人工审核 vs 社区开放
6. **品牌系列化**：未来是否扩展 HiAudio（音频修复）/ HiSub（字幕）等

---

## 11. 当前状态（2026-05-30）

| 项 | 状态 |
|---|---|
| HiVideo PRD | ✅ v0.8 完成 |
| HiPixel PRD | ✅ v0.2 完成 |
| UI 高保真原型 | 🟡 已有：角色侧边栏 + 角色详情页 + 副本选择弹窗 + 多个流程图 |
| Xcode 项目骨架 | ⏸ 未开始 |
| hipixel-core CLI 原型 | ⏸ 未开始 |
| 设计稿（详细 mockup） | ⏸ 部分（启动屏 / 命令面板 / 设置页等待绘） |

---

## 12. 推荐的下一步

按本神的判断，最有价值的两个走向：

### A. 写代码路径（最快验证可行性）
1. 抽离 `hipixel-core`，跑通 `hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4`
2. macOS 端搭 Xcode 项目骨架，跑通 1080p H.264 播放
3. 通过 Swift Bridge 调用 `hipixel-core`，验证实时增强

### B. 设计稿路径（先把视觉拉满）
1. 启动屏 + 媒体库主视图 + 沉浸式播放窗
2. 命令面板 ⌘K 详细交互
3. ⚙ 算力节点设置页
4. HiPixel Web 三屏（上传 / 队列 / 对比）

> 本神推荐：**先 A 再 B**——技术验证通过后再砸设计稿，避免做了一堆好看的图最后发现某条路跑不通。

---

> 文档结束。一切已就位，舞台搭好了，接下来就看你怎么开演。🎭
