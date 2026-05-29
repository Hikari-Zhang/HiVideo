# HiPixel · AI 视频画质增强服务（Web + Server）

> HiVideo 的姊妹产品。**HiVideo 是"看"，HiPixel 是"出"。**
> 把 AI 增强引擎从播放器独立出来，做成 Web 上传 / 提交任务 / 批量导出高画质视频文件的服务。

---

## 0. 文档信息

| 项 | 值 |
|---|---|
| 版本 | v0.2（设计稿，新增 Windows 平台一等公民支持） |
| 日期 | 2026-05-30 |
| 项目代号 | HiPixel |
| 与 HiVideo 关系 | 共享 AI 增强引擎核心，独立产品形态 |

---

## 1. 定位与差异

### 1.1 一句话定位
> **「上传 → 选预设 → 等待 → 下载」的最简 AI 视频画质增强服务。**

### 1.2 与 HiVideo 的差异

| 维度 | HiVideo | HiPixel |
|---|---|---|
| 形态 | macOS 桌面播放器 | Web 前端 + Server 后端 |
| 场景 | 实时观看时增强 | 离线批量增强并导出文件 |
| 输出 | 当下屏幕渲染 | 成品 mp4 / mov / mkv 文件 |
| 算力 | 用户自己的 Mac | 用户自部署 / 厂商托管 |
| 体验目标 | 0 等待、0 操作 | 可控参数、可批量、可定时 |
| 用户 | 普通看片用户 | 摄影师 / 创作者 / 影视修复工作室 / 老片爱好者 |

### 1.3 共享 vs 独立

**共享 HiVideo 核心**：
- 同一套 AI 模型权重（Real-ESRGAN / Anime4K / NAFNet / RIFE / DeOldify…）
- 同一套滤镜参数语义
- 同一套预设规则

**独立部分**：
- Web 前端（React / Vue）
- Server 调度（任务队列 / GPU 调度 / 鉴权）
- 文件存储与传输（断点续传 / 大文件优化）
- 计费与额度（如做商业化）

---

## 2. 用户画像与场景

### 2.1 目标用户

- **个人创作者**：B 站 UP / YouTube 博主，把老素材 1080p 升 4K
- **影视修复爱好者**：DVD 收藏党，批量修复老片
- **小工作室**：婚庆 / 短视频公司，量产升画质素材
- **不愿装客户端的偶发用户**：只想升一个视频，懒得装播放器

### 2.2 关键场景

| 场景 | 痛点 | 我们的解法 |
|---|---|---|
| 想把 100 集老剧批量升 1080p | 桌面工具一个个跑 | Web 排队，提交后该干嘛干嘛 |
| 在公司机器上想快速试用 | 不能装新软件 | 浏览器打开就用 |
| 自己 Mac 不够强，想用台式机算力 | 跨设备麻烦 | 自部署 Server，浏览器在 Mac 用 |
| 想给朋友升一段视频 | 微信传文件 + 桌面工具，麻烦 | 发个 HiPixel 链接（短期共享） |

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Web 前端（React + Vite）                                   │
│  • 上传 / 拖拽                                              │
│  • 任务进度 / 队列                                          │
│  • 参数预设 / 自定义                                        │
│  • 预览（before / after）                                   │
│  • 结果下载 / 分享链接                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTPS · REST + WebSocket（SSE 进度）
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  API Gateway（FastAPI / Fiber）                            │
│  • 鉴权（JWT / OAuth / API Key）                           │
│  • 限流 / 配额                                              │
│  • 任务编排                                                  │
└────┬───────────────────┬───────────────────┬────────────────┘
     │                   │                   │
     ▼                   ▼                   ▼
┌─────────────┐   ┌──────────────┐   ┌────────────────┐
│ 任务队列     │   │ 对象存储     │   │ 元数据库       │
│ Redis Stream │   │ S3 兼容     │   │ PostgreSQL     │
│ 或 RabbitMQ  │   │ 原始/输出   │   │ 用户/任务/配额 │
└──────┬──────┘   └──────┬──────┘   └────────────────┘
       │                 │
       ▼                 │
┌─────────────────────────────────────────────────────────────┐
│  Worker 集群（Python / Rust）                               │
│  • 拉任务 → 拉源文件 → 调推理 → 转码 → 推结果              │
│  • GPU 调度（PyTorch / ONNX Runtime / CoreML 跨平台）       │
│  • 进度回报（SSE）                                          │
└─────────────────────────────────────────────────────────────┘
       ▲
       │
┌──────┴──────────────────────────────────────────────────────┐
│  GPU 节点                                                   │
│  • Apple Silicon（CoreML / MPS）                            │
│  • NVIDIA（CUDA / TensorRT）                                │
│  • Intel Arc（OpenVINO）                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 部署形态（三选一）

| 形态 | 适用 | 特点 |
|---|---|---|
| **Windows 一键安装包** | 家用 RTX 工作站 / 闲置 PC 复用 | exe 安装 + 托盘 UI + mDNS 广播，最简启动 |
| **macOS 应用包** | Mac mini 当家庭 GPU 节点 | dmg 安装 + 菜单栏图标 + Bonjour 广播 |
| **Docker Compose 单机** | NAS / Linux 服务器 | 一键起，最低 8GB 内存 + 一块 GPU |
| **Kubernetes 集群** | 工作室 / 团队 | 多 Worker 横向扩展，GPU 池化 |
| **托管云服务** | 偶发用户 | 我们运营，按时长 / 时段计费 |

---

## 4. 功能详细规范

### 4.1 上传与任务提交（P0）

#### 4.1.1 上传方式
- 拖拽到浏览器
- 点击选文件（多选）
- 粘贴 URL（HTTP / S3 / WebDAV）
- 直接上传 zip 批量压缩包
- 通过 API 提交（适合自动化流水线）

#### 4.1.2 文件支持
- 输入：MP4 / MOV / MKV / AVI / WebM / TS / FLV / ProRes / DNxHR
- 单文件上限：默认 10GB（部署可配）
- 批量：单次最多 50 个任务

#### 4.1.3 断点续传
- TUS 协议或自研分片
- 网络中断后可继续
- 已上传分片存对象存储，server 重启不丢

#### 4.1.4 大文件优化
- 用户本地 ffmpeg.wasm 先抽帧预览（仅元数据），秒级反馈
- 提供"无需上传，直接处理 NAS 上的视频"模式（Server 主动拉）

### 4.2 增强参数面板（P0）

#### 4.2.1 预设（一键应用）

继承 HiVideo 的预设，针对离线场景调优：

| 预设 | 内容 | 典型耗时（10min 1080p） |
|---|---|---|
| **老片救星** | 超分 ×2 + 降噪 + 锐化 | ~15 min（A100） / 45 min（M2） |
| **番剧增强** | Anime4K + 锐化 | ~5 min |
| **黑白复刻** | 上色 + 降噪 + 超分 | ~30 min |
| **HDR 兼容** | tone-mapping | ~3 min |
| **丝滑插帧 60fps** | RIFE | ~25 min |
| **极致修复** | 全套 + 高强度（GPU 重） | ~60 min |
| **最快速度** | 仅锐化（实时） | < 1 min |

#### 4.2.2 自定义参数
- 输出分辨率：1080p / 1440p / 4K / 8K / 自定义
- 输出帧率：保持 / 30 / 60 / 120
- 编码：H.264 / H.265 / AV1 / ProRes
- 码率模式：CRF（质量优先）/ ABR（指定码率）/ 无损
- 容器：MP4 / MOV / MKV
- HDR 元数据：保留 / SDR / HDR10
- 字幕：保留嵌入 / 烧录 / 移除
- 音频：原音 / 降噪 / 重采样

#### 4.2.3 高级
- 时间段裁切：仅处理 00:30-10:00
- 区域处理：仅处理画面右半部分（Watermark 修复用）
- 帧率匹配：23.976 → 24 → 25 / 反向 telecine
- 颜色空间转换：BT.601 / BT.709 / BT.2020

### 4.3 任务管理（P0）

#### 4.3.1 队列视图
- 排队中 / 处理中 / 完成 / 失败 四个标签
- 每个任务卡片：缩略图 / 文件名 / 进度条 / 预计剩余时间 / 当前阶段
- 可暂停 / 取消 / 重试 / 调整优先级

#### 4.3.2 进度颗粒度
- 阶段：上传 → 转码预处理 → AI 推理（按帧）→ 转码输出 → 上传结果
- AI 阶段实时回报百分比 + 当前帧号 + GPU 利用率
- 失败时显示失败原因 + 失败帧号

#### 4.3.3 通知
- 浏览器桌面通知
- 邮件通知（任务 > 5 分钟）
- Webhook 回调（开发者）
- iOS / Android 推送（如做 PWA）

### 4.4 预览与对比（P0）

#### 4.4.1 实时预览（不耗算力）
- 上传后立即抽 5 帧关键帧
- 用 wasm 跑轻量超分模型，本地预览效果（约 1080p 5 帧 < 10s）
- 点击播放对比小窗：拖动分割线左右对比

#### 4.4.2 处理后对比
- 任务完成后，左 = 原片 / 右 = 增强版
- 同步播放 + 同步进度条
- 截图保存对比图（带水印 / 不带）

#### 4.4.3 关键帧报告
- 自动选 6-12 个差异最大帧
- 标注哪些区域被超分 / 降噪 / 上色
- 适合给客户验收用

### 4.5 结果交付（P0）

- 浏览器直接下载（HTTP Range）
- 分享链接（短链 + 7 天有效，可设密码）
- 自动推送到指定网盘（WebDAV / S3 / Google Drive）
- API 拉取（适合下游流水线）
- 大文件分片下载（兼容下载工具）

### 4.6 用户与配额（P1）

#### 4.6.1 用户体系
- 邮箱 / OAuth（Google / GitHub / Apple）
- 自部署可关闭注册，仅管理员添加
- 多用户 + 团队 / 项目分组

#### 4.6.2 配额
- 每日 / 每月 GPU 分钟数
- 单文件大小上限
- 并发任务数
- 存储空间
- 输出保留期（默认 7 天）

#### 4.6.3 计费（如商业化）
- 按 GPU 分钟数计费（不同模型不同费率）
- 阶梯：免费 30 分钟/月 / Pro 500 分钟 / 团队定制
- 充值卡 / 订阅 / 企业月结

### 4.7 API & SDK（P1）

#### 4.7.1 REST API
```
POST   /v1/tasks          提交任务
GET    /v1/tasks/:id      查询任务
DELETE /v1/tasks/:id      取消任务
GET    /v1/tasks          列出任务（分页 / 过滤）
GET    /v1/tasks/:id/output  下载结果（302 → 预签名 URL）
POST   /v1/uploads        发起上传（返回 TUS 端点）
```

#### 4.7.2 WebSocket / SSE
- `/v1/tasks/:id/progress` 实时进度推送

#### 4.7.3 SDK
- 官方：Python / TypeScript
- 社区：Go / Rust / Swift（HiVideo 直接用）

#### 4.7.4 命令行工具
```bash
hipixel up movie.mp4 --preset old-film-revival
hipixel ls
hipixel get <task-id> -o ./output/
```

### 4.8 GPU 调度与扩展性（P0）

#### 4.8.1 异构 GPU 支持
- **NVIDIA**：CUDA + TensorRT 加速（推理性能最高，**Windows 主力**）
- **Apple Silicon**：CoreML + MPS（家庭 NAS / Mac mini 部署）
- **Intel Arc / 集成 GPU**：OpenVINO（中端机型，Windows / Linux）
- **AMD Radeon**：DirectML（Windows 专属路径） / ROCm（Linux）
- **CPU 兜底**：仅最快速度预设

#### 4.8.2 调度策略
- 任务 → 资源亲和（HDR 处理优先 NVIDIA，番剧优先 Apple）
- 优先级队列：付费用户 > 免费用户 > 后台任务
- 自动故障转移：Worker 崩溃任务自动迁移
- 弹性扩缩容（K8s + HPA on GPU 利用率）

#### 4.8.3 模型管理
- Worker 启动时按需拉取模型（共享卷）
- 模型版本固定（不会半夜被换）
- A/B 测试：新版模型先在 5% 流量验证

### 4.9 安全与隐私（P0）

| 维度 | 措施 |
|---|---|
| 传输 | HTTPS 强制 + HSTS |
| 存储 | 对象存储服务端加密 + 用户密钥可选客户端加密 |
| 鉴权 | JWT 短期 token + refresh / API Key 双信道 |
| 隔离 | 每个用户独立 bucket 前缀 |
| 自动清理 | 默认 7 天自动删源文件和输出 |
| 私密模式 | "处理完即删，不入日志、不入预览缓存" |
| 审计 | 所有 API 调用记录（脱敏） |
| 合规 | GDPR 数据导出 / 删除接口 |

### 4.10 与 HiVideo 的双向集成（P1）

- HiVideo 客户端内右键视频 → 「发送到 HiPixel 增强」
- HiPixel 处理完 → 自动回传到 HiVideo 媒体库（同一 MediaItem 的新 Variant）
- HiVideo 续播 / 字幕 / 标签等元数据共享
- 一个账号通用

### 4.11 Windows 平台支持（P0）

> **HiPixel 是跨平台的**——Web 前端天然跨平台，Server 端把 Windows 列为一等公民部署目标。家里那台带 RTX 显卡的 Windows 工作站，跑 AI 增强比 Mac 强得多，必须能直接用上。

#### 4.11.1 为什么要重视 Windows

| 理由 | 说明 |
|---|---|
| **NVIDIA 显卡装机率高** | RTX 30/40/50 系几乎都在 Windows 工作站 |
| **TensorRT 性能最强** | 同样的 Real-ESRGAN 模型，RTX 4090 比 M2 Max 快 5-10× |
| **用户已有硬件** | 不强迫买新机，把闲置 PC 变成 GPU 节点 |
| **HiVideo 反向受益** | Mac 上的 HiVideo 能调用家里 Windows 的 HiPixel 跑大任务 |

#### 4.11.2 三种 Windows 部署形态

**A. 一键安装包（最简，主推）**

- 提供 `HiPixel-Setup-x.y.z.exe` 安装程序
- 内置：Python 运行时 / FFmpeg / Redis Embedded / SQLite / NVIDIA 驱动检测
- 安装时自动检测 GPU 并下载对应推理后端：
  - 检测到 RTX 30/40/50 → 拉 CUDA 12 + TensorRT
  - 检测到 GTX → 拉 CUDA 12（无 TensorRT）
  - 检测到 AMD Radeon → 拉 DirectML
  - 检测到 Intel Arc → 拉 OpenVINO
  - 仅核显 → 提示 CPU 模式或升级硬件
- 安装后系统托盘有图标，右键「打开 Web UI / 暂停 / 退出」
- 双击托盘 → 浏览器自动打开 `http://localhost:7860`
- 同时在局域网广播（mDNS / Bonjour），Mac 上的 HiVideo 自动发现

**B. WSL2 + Docker（开发者友好）**

- 提供官方 `docker compose` 文件
- WSL2 提供原生 Linux 容器环境
- NVIDIA Container Toolkit 让容器直接用 GPU
- 适合熟悉命令行的用户和云端混合部署

**C. 纯命令行 / 服务模式（高级）**

- `hipixel-server.exe --service install` 注册为 Windows 服务
- 开机自启，后台运行，无 UI
- 适合 NAS 化使用的小型工作站

#### 4.11.3 GPU 后端选择矩阵（Windows）

| 显卡 | 主用后端 | 备用 | 性能（1080p Real-ESRGAN） |
|---|---|---|---|
| RTX 4090 / 5090 | TensorRT FP16 | CUDA | **5-8× 实时** |
| RTX 4070 / 4080 | TensorRT FP16 | CUDA | 3-5× 实时 |
| RTX 3060-3080 | TensorRT FP16 | CUDA | 1.5-3× 实时 |
| GTX 16 系 | CUDA FP32 | DirectML | 0.4-0.8× 实时 |
| AMD RX 7000 系 | DirectML | ROCm（WSL） | 1-2× 实时 |
| AMD RX 6000 系 | DirectML | — | 0.5-1× 实时 |
| Intel Arc A 系 | OpenVINO | DirectML | 0.5-1× 实时 |
| Intel 集显 | OpenVINO | CPU | 0.1-0.3× 实时 |

> 数字为参考值，实际取决于具体型号、显存、视频内容复杂度。

#### 4.11.4 Windows 特有功能

- **NVENC / AV1 硬编码**：用 NVIDIA 显卡的 NVENC 出片，比 CPU 编码快 10×
- **AMF（AMD）/ Quick Sync（Intel）** 硬编码同样支持
- **托盘 UI**：暂停 / 队列 / 显存监视 / GPU 温度
- **NVIDIA Broadcast 集成**（可选）：用户可选择走 Broadcast SDK 做高质量降噪
- **DirectStorage**：4K 大文件读取走 NVMe 直通，减少 CPU 占用
- **Windows ML**：作为 DirectML 的封装层，可调用 Windows 自带的优化

#### 4.11.5 跨平台一致性保证

| 层 | 一致性策略 |
|---|---|
| 模型权重 | 同一 ONNX 文件，转换为各后端格式（TRT / DirectML / OpenVINO） |
| 滤镜参数 | 完全相同语义，不同后端跑同一参数得到几乎一致结果 |
| 一致性测试 | CI 跑同一段标准视频，对比 PSNR / SSIM 不能差超 0.5dB |
| 预设定义 | JSON 描述文件，跨平台共享 |
| API 行为 | REST 端点一致，差异仅在性能和支持的具体后端 |

#### 4.11.6 Windows 安装包细节

| 项 | 规范 |
|---|---|
| 包大小（基础） | < 200MB（不含模型，按需下载） |
| 模型下载位置 | `%LOCALAPPDATA%\HiPixel\models\` |
| 数据存储位置 | `%LOCALAPPDATA%\HiPixel\data\`（可改） |
| 默认端口 | 7860（可改） |
| 端口冲突 | 自动找空闲端口 + 通知用户 |
| 防火墙 | 安装时申请入站规则（仅局域网） |
| 卸载 | 标准卸载程序 + 可选清除模型/数据 |
| 自动更新 | Sparkle for Windows 风格静默更新（可关） |
| 数字签名 | EV Code Signing，避免 SmartScreen 警告 |

#### 4.11.7 与 macOS HiVideo 联动

```
家里：Windows 工作站（RTX 4090）跑 HiPixel Server
        ↓ mDNS 局域网广播
办公：MacBook 上的 HiVideo 自动发现「家里的 RTX 4090」
        ↓ 用户在 HiVideo 里右键 →「发送到家里的 GPU」
        ↓ 视频通过 SMB / 直链发送
HiPixel 在家里跑增强（5× 实时）
        ↓ 完成后回传 MacBook
HiVideo 媒体库出现新 Variant（4K 增强版）
```

- 局域网内零配置发现（mDNS）
- 公网通过 WireGuard / Tailscale 远程访问家里的 HiPixel
- 全程 AES-256 端到端加密（如启用公网模式）

#### 4.11.8 性能对比基准（参考）

| 配置 | 1080p 老片救星 10min | 4K 极致修复 10min |
|---|---|---|
| RTX 4090 + DDR5 | ~3 min | ~12 min |
| RTX 4070 + DDR5 | ~6 min | ~25 min |
| M2 Max（Mac mini） | ~8 min | ~40 min |
| RTX 3060 + DDR4 | ~10 min | ~45 min |
| AMD RX 7800 XT | ~9 min | ~38 min |
| Intel Arc A770 | ~12 min | ~55 min |
| 仅 CPU（i7-13700K） | ~120 min | 不推荐 |

#### 4.11.9 与 Linux Server 的代码共享

- 核心 Python 代码 100% 共享（PyTorch / FastAPI / FFmpeg-python）
- 仅 GPU 后端入口层不同：
  - Linux：CUDA / ROCm / OpenVINO
  - Windows：CUDA / TensorRT / DirectML / OpenVINO
- CI 矩阵：每个 PR 跑 ubuntu-latest + windows-latest 双平台测试
- 安装包通过 PyInstaller / Nuitka 打包

---

## 5. UI 设计原则

### 5.1 三屏极简

**① 上传屏**
- 大留白 + 中央拖拽区
- 选择预设（6 张大卡片）
- 「开始增强」主按钮

**② 队列屏**
- 任务列表（缩略图 + 进度环 + 状态徽章）
- 完成的任务有「下载 / 对比 / 分享」三按钮
- 失败的任务一键重试

**③ 对比屏**
- 左右分屏 + 拖动比较条
- 同步进度条
- 关键帧报告侧栏

### 5.2 视觉语言
- 浅色 / 深色随系统
- 主色：紫色（与 HiVideo 区分，但同源调性）
- 字体：Inter（Web 通用）/ SF Pro（macOS）
- 圆角：8px / 12px

---

## 6. 性能目标

| 指标 | 目标（NVIDIA A10）| 目标（M2 Max） |
|---|---|---|
| 1080p 老片救星预设 | 1.5× 实时 | 0.5× 实时 |
| 1080p 番剧 Anime4K | 6× 实时 | 3× 实时 |
| 4K 极致修复 | 0.3× 实时 | 0.1× 实时 |
| 任务启动开销 | < 5s | < 5s |
| 上传 1GB 视频 | 取决于带宽，断点续传 | — |
| Web 首屏 LCP | < 2s | — |

---

## 7. 技术栈选型

| 层 | 候选 | 决定 |
|---|---|---|
| Web 前端 | React + Vite + Tailwind / Vue 3 + Vite | **React + Vite + shadcn/ui**（生态广） |
| 状态管理 | Zustand / Redux | Zustand |
| API 层 | FastAPI / Fiber / NestJS | **FastAPI**（与 AI 生态契合） |
| 任务队列 | Redis Stream / RabbitMQ / Celery | Redis Stream（最简） |
| 数据库 | PostgreSQL | ✓ |
| 对象存储 | MinIO / S3 / R2 | MinIO 自部署 / S3 兼容协议 |
| 视频处理 | FFmpeg + ffmpeg-python | ✓ |
| AI 推理 | PyTorch / ONNX Runtime / TensorRT / CoreML | 按 GPU 选 |
| 监控 | Prometheus + Grafana | ✓ |
| 部署 | Docker / K8s / Helm | 提供两套 chart |

---

## 8. 开发路线图

### Phase 0 · 内核抽离（3 周）
- 把 HiVideo 的增强引擎抽成独立 `hipixel-core` 库
- 提供 CLI：`hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4`
- 跨 GPU 支持（CUDA / MPS / OpenVINO）

### Phase 1 · MVP Web（5 周）
- 单机 Docker Compose 部署
- 上传 / 提交 / 队列 / 下载基本流程
- 5 个预设
- 浏览器直传 + 直下载

### Phase 2 · 分布式 & 多用户（4 周）
- 任务队列 + Worker 集群
- 用户体系 + 配额
- API / SDK

### Phase 3 · 体验闭环（4 周）
- 预览对比 + 关键帧报告
- 通知 + Webhook
- 与 HiVideo 双向集成

### Phase 4 · 商业化 / 部署（4 周）
- 计费系统（如做云服务）
- K8s Helm chart
- 官网 + 文档

**Beta 上线**：Phase 2 完成后
**正式 v1.0**：Phase 4 完成

---

## 9. 与 HiVideo 共建的工程边界

```
┌─────────────────────────────────────┐
│  hipixel-core (Rust + Python)       │
│  • 模型加载与推理                    │
│  • 视频解码 / 编码                   │
│  • 增强滤镜流水线                    │
│  • 预设定义                          │
└─────────────────────────────────────┘
        ▲                ▲
        │                │
   ┌────┴────┐      ┌────┴────┐
   │ HiVideo │      │ HiPixel │
   │ (Swift) │      │ (Web +  │
   │         │      │  Server)│
   └─────────┘      └─────────┘
```

- 共享语义：滤镜参数 / 预设 / 模型版本
- 一处更新，两端共享
- HiVideo 通过 Swift 包装 hipixel-core 实时调用
- HiPixel 通过 Python wrapper 批量调用

---

## 10. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| GPU 资源昂贵 | 高 | 高 | 自部署优先，托管做高利润高端档 |
| 上传带宽瓶颈 | 中 | 高 | 支持远程拉取（NAS/S3 直连）+ 断点续传 |
| 任务时长不可预测 | 中 | 中 | 用历史数据预测剩余时间 + 批量任务通知 |
| 模型版权 | 中 | 高 | 仅使用允许商用的开源模型 / 自训练 |
| 用户隐私敏感 | 中 | 高 | 私密模式 + 自部署优先推广 |
| 与 HiVideo 概念混淆 | 中 | 中 | 文案明确区分"看 vs 出"，独立官网 |

---

## 11. 商业化候选模式（开放）

1. **完全开源 + 自部署**：建立社区，靠周边盈利
2. **开源核心 + 托管 SaaS**：核心免费自部署，SaaS 按 GPU 分钟计费
3. **商业闭源**：Pro 用户买断，企业月结
4. **HiVideo 增值订阅**：作为 HiVideo Pro 的赠品功能（通过云端 GPU 跑大任务）

> 推荐 **#2 开源核心 + 托管 SaaS**：扩散最快，付费意愿明确。

---

> 文档结束。下一步建议：把 hipixel-core 抽离做出 CLI 原型，跑通"输入 mp4 → 老片救星预设 → 输出 mp4"端到端流程，验证模型在不同 GPU 上的实际性能。
