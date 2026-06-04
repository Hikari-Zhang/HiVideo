# hipixel-core · 系统设计文档

> **版本**：v0.1（与 DEV-PLAN Phase 0 对应，Python 优先实现）
> **日期**：2026-05-30
> **状态**：设计稿，待 Phase 0 开发过程中持续修订

---

## 目录

1. [定位与边界](#1-定位与边界)
2. [整体架构](#2-整体架构)
3. [模块设计](#3-模块设计)
   - 3.1 [InferenceBackend · GPU 后端抽象](#31-inferencebackend--gpu-后端抽象)
   - 3.2 [Video I/O 层](#32-video-io-层)
   - 3.3 [Filter 协议 与 Pipeline](#33-filter-协议与-pipeline)
   - 3.4 [预设系统](#34-预设系统)
   - 3.5 [模型管理器](#35-模型管理器)
   - 3.6 [CLI 层](#36-cli-层)
4. [核心数据模型](#4-核心数据模型)
5. [关键流程](#5-关键流程)
6. [性能设计](#6-性能设计)
7. [跨平台策略](#7-跨平台策略)
8. [错误处理](#8-错误处理)
9. [测试策略](#9-测试策略)
10. [Phase 2.5 Rust 迁移路径](#10-phase-25-rust-迁移路径)

---

## 1. 定位与边界

### 1.1 是什么

`hipixel-core` 是 HiVideo / HiPixel 共享的 AI 视频增强引擎库。它的职责是：

```
接收原始视频文件
    → 按预设/自定义参数组装滤镜流水线
    → 逐帧调用 AI 模型推理（超分 / 降噪 / 插帧 / 上色）
    → 输出增强后的视频文件
```

### 1.2 不是什么

| 不负责 | 由谁负责 |
|---|---|
| Web 前端 / 任务队列 / 鉴权 | HiPixel Server（FastAPI） |
| 播放器 UI / 媒体库管理 | HiVideo（SwiftUI） |
| 视频字幕生成 / 对齐 | HiVideo AIKit（Whisper） |
| 角色识别 / 场景分类 | HiVideo AIKit（CLIP / ArcFace） |
| 文件元数据刮削 | HiVideo MediaKit（TMDB 插件） |

### 1.3 消费者

```
HiVideo (Swift)                HiPixel Server (Python)
      │                                  │
      │ Swift FFI（Phase 2.5+）          │ import hipixel_core
      │ UniFFI 生成的 .swift 绑定         │ Python 直接调用
      └──────────────┬───────────────────┘
                     ▼
              hipixel-core
              (Python 优先 → Rust 内核 Phase 2.5)
```

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI 层                               │
│  hipixel-core enhance / batch / presets / models / bench    │
│  (Typer + Rich)                                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Pipeline 编排层                           │
│  Preset → FilterChain → ProgressCallback → OutputSpec       │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────────┐
│  Video I/O  │  │  Filter 集合    │  │  Model Manager │
│  Decoder    │  │  RealESRGAN     │  │  下载 / 缓存   │
│  Encoder    │  │  Anime4K        │  │  版本锁定      │
│  帧格式转换  │  │  NAFNet         │  │  哈希校验      │
└──────┬──────┘  │  CAS / RIFE     │  └────────────────┘
       │         │  DeOldify       │
       │         └────────┬────────┘
       │                  │
┌──────▼──────────────────▼──────────────────────────────────┐
│                  InferenceBackend 抽象层                     │
│  GPU 自动检测 → 选择最优后端                                  │
├────────────┬──────────────┬────────────┬────────────────────┤
│ CoreML/MPS │  CUDA/ONNX   │ DirectML   │   CPU 兜底         │
│ Apple      │  NVIDIA      │ Windows    │   任意平台          │
│ Silicon    │  Linux/Win   │ AMD/Intel  │                    │
└────────────┴──────────────┴────────────┴────────────────────┘
```

---

## 3. 模块设计

### 3.1 InferenceBackend · GPU 后端抽象

#### 职责

屏蔽不同平台 / 显卡的推理差异，向上层 Filter 提供统一的"加载模型 → 运行推理"接口。

#### Protocol 定义

```python
# hipixel_core/backends/base.py

from typing import Protocol, runtime_checkable
import numpy as np

@runtime_checkable
class InferenceBackend(Protocol):
    """GPU 推理后端协议。所有后端必须实现此接口。"""

    @property
    def name(self) -> str:
        """后端标识符，如 'coreml', 'cuda', 'cpu'"""
        ...

    @property
    def device_info(self) -> "DeviceInfo":
        """设备信息：型号、可用显存、驱动版本"""
        ...

    def load_model(self, model_path: str, model_key: str) -> None:
        """加载 ONNX 模型到设备。model_key 用于缓存引用。"""
        ...

    def unload_model(self, model_key: str) -> None:
        """从设备显存卸载模型。"""
        ...

    def run(
        self,
        inputs: dict[str, np.ndarray],
        model_key: str,
    ) -> dict[str, np.ndarray]:
        """执行推理。inputs/outputs 均为 numpy 数组（CPU 侧）。
        实现内部负责 CPU→GPU 上传和 GPU→CPU 下载。
        """
        ...

    def available_vram_mb(self) -> int:
        """当前可用显存（MB）。CPU 后端返回可用内存。"""
        ...

    def warmup(self, model_key: str, input_shape: tuple) -> None:
        """预热模型（CoreML / TensorRT 首次推理延迟高，提前触发编译）。"""
        ...
```

#### 后端选择策略

```python
# hipixel_core/backends/selector.py

BACKEND_PRIORITY = [
    ("coreml",   _is_apple_silicon),   # M 系芯片首选
    ("cuda",     _has_cuda_gpu),        # NVIDIA GPU
    ("directml", _is_windows_dml),      # Windows AMD/Intel
    ("openvino", _has_intel_gpu),       # Intel Arc / VPU
    ("cpu",      lambda: True),         # 兜底
]

def select_backend(prefer: str | None = None) -> InferenceBackend:
    if prefer:
        return _instantiate(prefer)
    for name, probe in BACKEND_PRIORITY:
        if probe():
            return _instantiate(name)
```

#### 各后端实现要点

| 后端 | 推理引擎 | 模型格式 | 适用平台 |
|---|---|---|---|
| `CoreMLBackend` | `coremltools` + MPS | `.mlpackage`（从 ONNX 转换） | macOS 12+ Apple Silicon |
| `CUDABackend` | `onnxruntime-gpu`（CUDAExecutionProvider） | `.onnx` | Linux/Windows NVIDIA |
| `DirectMLBackend` | `onnxruntime-directml` | `.onnx` | Windows AMD/Intel |
| `OpenVINOBackend` | `onnxruntime-openvino` | `.onnx` | Linux/Windows Intel |
| `CPUBackend` | `onnxruntime`（CPUExecutionProvider） | `.onnx` | 任意 |

---

### 3.2 Video I/O 层

#### 职责

- **Decoder**：从文件/URL 解复用、解码，输出帧流（`Iterator[VideoFrame]`）
- **Encoder**：消费帧流，编码并封装为目标容器
- **帧格式转换**：YUV ↔ RGB ↔ float32 tensor

#### Decoder

```python
# hipixel_core/video/decoder.py

@dataclass
class DecoderConfig:
    hw_accel: bool = True          # VideoToolbox / NVDEC 硬解
    seek_to: float | None = None   # 起始时间（秒）
    end_at: float | None = None    # 结束时间（秒）
    target_fps: float | None = None  # 强制抽帧到目标帧率

class VideoDecoder:
    def __init__(self, path: str, config: DecoderConfig = DecoderConfig()): ...

    @property
    def meta(self) -> "VideoMeta":
        """分辨率 / 帧率 / 时长 / 编码 / 色彩空间 / HDR 元数据"""
        ...

    def frames(self) -> Iterator["VideoFrame"]:
        """惰性帧流。每帧解码按需，不预读整个文件。"""
        ...

    def keyframes(self, count: int = 6) -> list["VideoFrame"]:
        """抽取 N 帧关键帧（用于预览）。"""
        ...
```

#### Encoder

```python
# hipixel_core/video/encoder.py

@dataclass
class EncoderConfig:
    codec: Literal["h264", "h265", "av1", "prores"] = "h265"
    crf: int = 18                      # 质量优先模式
    bitrate_kbps: int | None = None    # ABR 模式（与 crf 二选一）
    container: Literal["mp4", "mkv", "mov"] = "mp4"
    hw_encode: bool = True             # NVENC / VideoToolbox 硬编
    audio: Literal["copy", "denoise", "resample", "strip"] = "copy"
    subtitle: Literal["copy", "burn", "strip"] = "copy"
    hdr_mode: Literal["preserve", "tonemap_sdr", "hdr10"] = "preserve"
    colorspace: str | None = None      # 强制色彩空间转换

class VideoEncoder:
    def __init__(self, output_path: str, source_meta: "VideoMeta",
                 config: EncoderConfig = EncoderConfig()): ...

    def write_frame(self, frame: "VideoFrame") -> None: ...

    def finalize(self) -> "EncodeResult":
        """完成编码，返回输出文件信息（大小 / 时长 / 实际编码参数）。"""
        ...

    def __enter__(self) -> "VideoEncoder": ...
    def __exit__(self, *_) -> None: ...
```

---

### 3.3 Filter 协议与 Pipeline

#### Filter Protocol

每个滤镜是无状态的处理单元，状态（模型权重）在 `InferenceBackend` 中管理。

```python
# hipixel_core/filters/base.py

@dataclass
class FilterParams:
    """滤镜参数基类。各滤镜定义自己的子类。"""
    pass

@runtime_checkable
class Filter(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def required_models(self) -> list[str]:
        """需要预加载的模型 key 列表。"""
        ...

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        """在流水线开始前调用：模型加载、参数校验、预热。"""
        ...

    def process_frame(
        self,
        frame: "VideoFrame",
        backend: InferenceBackend,
        params: FilterParams,
    ) -> "VideoFrame":
        """处理单帧。必须是幂等的（不修改输入）。"""
        ...

    def teardown(self, backend: InferenceBackend) -> None:
        """流水线结束后调用：释放模型、清理显存。"""
        ...

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        """预估处理该分辨率所需显存（MB），用于显存不足时的降级决策。"""
        ...
```

#### FilterInstance（携带参数的滤镜实例）

```python
@dataclass
class FilterInstance:
    filter: Filter
    params: FilterParams
    enabled: bool = True
```

#### Pipeline

```python
# hipixel_core/pipeline.py

@dataclass
class PipelineConfig:
    backend: InferenceBackend
    filters: list[FilterInstance]
    output: "OutputSpec"
    progress_callback: Callable[["ProgressEvent"], None] | None = None

class Pipeline:
    def __init__(self, config: PipelineConfig): ...

    def setup(self) -> None:
        """按顺序调用所有 filter.setup()，检查显存是否足够。"""
        ...

    def run(self, decoder: VideoDecoder, encoder: VideoEncoder) -> "PipelineResult":
        """
        主循环：
          for frame in decoder.frames():
              for filter_instance in self.filters:
                  frame = filter_instance.filter.process_frame(frame, ...)
              encoder.write_frame(frame)
        """
        ...

    def teardown(self) -> None:
        """反序调用所有 filter.teardown()，释放显存。"""
        ...

    @classmethod
    def from_preset(cls, preset: "Preset", backend: InferenceBackend) -> "Pipeline":
        """从预设构建流水线（工厂方法）。"""
        ...
```

#### 内置滤镜一览

| 类名 | 算法 | 模型 | 主要参数 |
|---|---|---|---|
| `RealESRGANFilter` | 超分辨率 | `RealESRGAN_x2plus.onnx` / `_x4plus.onnx` | `scale: 2\|4`, `tile_size`, `tile_padding` |
| `Anime4KFilter` | 动漫超分 | `Anime4K_CNN_x2.onnx` | `scale: 2\|4`, `strength` |
| `NAFNetFilter` | 降噪 | `NAFNet-REDS-width64.onnx` | `strength: 0.0-1.0` |
| `CASFilter` | 自适应锐化 | 无（GPU shader） | `sharpness: 0.0-1.0` |
| `RIFEFilter` | 光流插帧 | `RIFE_v4.6.onnx` | `target_fps: 60\|120`, `scene_cut_threshold` |
| `DeOldifyFilter` | 视频上色 | `DeOldify_video.onnx` | `render_factor: 21-44` |
| `ACESFilter` | HDR tone-mapping | 无（数学变换） | `exposure`, `gamma` |

---

### 3.4 预设系统

#### JSON Schema

```json
{
  "$schema": "https://hipixel.dev/schemas/preset/v1.json",
  "id": "old-film-revival",
  "name": "老片救星",
  "name_en": "Old Film Revival",
  "description": "超分 ×2 + 降噪 + 锐化，适合 DVDrip / VHS 老片修复",
  "version": "1.0.0",
  "tags": ["restoration", "superres", "denoise"],

  "filters": [
    {
      "filter": "nafnet",
      "params": { "strength": 0.6, "model": "NAFNet-REDS-width64" }
    },
    {
      "filter": "real_esrgan",
      "params": {
        "scale": 2,
        "model": "RealESRGAN_x2plus",
        "tile_size": 512,
        "tile_padding": 32
      }
    },
    {
      "filter": "cas",
      "params": { "sharpness": 0.4 }
    }
  ],

  "output": {
    "resolution": "2x",
    "fps": "preserve",
    "codec": "h265",
    "crf": 18,
    "container": "mp4",
    "audio": "copy"
  },

  "requirements": {
    "min_vram_mb": 4096,
    "recommended_vram_mb": 8192,
    "min_storage_multiplier": 3.0
  },

  "perf_estimate": {
    "A100_1080p_realtime_ratio": 1.5,
    "M2_1080p_realtime_ratio": 0.5,
    "RTX4090_1080p_realtime_ratio": 5.0
  }
}
```

#### 预设管理器

```python
# hipixel_core/presets/manager.py

class PresetManager:
    BUILTIN_DIR = Path(__file__).parent / "builtin"
    USER_DIR = Path.home() / ".hipixel" / "presets"

    def list(self) -> list[PresetMeta]: ...

    def get(self, preset_id: str) -> Preset:
        """先查 USER_DIR（用户可覆盖内置预设），再查 BUILTIN_DIR。"""
        ...

    def load_from_file(self, path: str) -> Preset: ...

    def validate(self, preset: Preset) -> list[ValidationError]:
        """检查：滤镜名合法 / 模型存在 / 参数在范围内。"""
        ...
```

#### 内置预设列表

| ID | 名称 | 滤镜组合 | 最低显存 |
|---|---|---|---|
| `old-film-revival` | 老片救星 | NAFNet → RealESRGAN×2 → CAS | 4GB |
| `anime-enhance` | 番剧增强 | Anime4K×2 → CAS | 2GB |
| `bw-colorize` | 黑白复刻 | DeOldify → NAFNet → RealESRGAN×2 | 6GB |
| `hdr-compat` | HDR 兼容 | ACES tone-map | 512MB |
| `smooth-60fps` | 丝滑插帧 60fps | RIFE×2 | 4GB |
| `extreme-restore` | 极致修复 | NAFNet → RealESRGAN×4 → CAS → RIFE | 10GB |
| `fast-sharpen` | 最快速度 | CAS | 256MB |

---

### 3.5 模型管理器

#### 职责

- 维护模型目录：`~/.hipixel/models/`
- 按需下载（首次使用时自动触发，或 `hipixel-core models download`）
- SHA-256 完整性校验
- 版本锁定（`models.lock.json`）
- CoreML 转换缓存（`.mlpackage` 在本地生成并缓存）

#### 模型注册表（`models.registry.json`）

```json
{
  "RealESRGAN_x2plus": {
    "filename": "RealESRGAN_x2plus.onnx",
    "sha256": "a1b2c3...",
    "size_mb": 64,
    "download_url": "https://models.hipixel.dev/v1/RealESRGAN_x2plus.onnx",
    "license": "BSD-3-Clause",
    "input_shape": ["batch", 3, "H", "W"],
    "output_shape": ["batch", 3, "2H", "2W"]
  }
}
```

#### 模型管理器接口

```python
# hipixel_core/models/manager.py

class ModelManager:
    def ensure(self, model_key: str, progress: ProgressCallback | None = None) -> Path:
        """确保模型可用（本地存在 + 校验通过），不存在则下载。返回本地路径。"""
        ...

    def ensure_all(self, model_keys: list[str]) -> None:
        """批量确保（并行下载）。"""
        ...

    def list_local(self) -> list[ModelInfo]: ...

    def list_available(self) -> list[ModelInfo]: ...

    def remove(self, model_key: str) -> None: ...

    def get_coreml_path(self, model_key: str) -> Path:
        """返回 CoreML .mlpackage 路径，若不存在则从 ONNX 转换并缓存。"""
        ...
```

---

### 3.6 CLI 层

基于 **Typer**（Click 上层封装），**Rich** 负责进度条和彩色输出。

#### 命令树

```
hipixel-core
├── enhance <input> -o <output> [--preset ID] [--backend NAME]
│                               [--resolution WxH] [--fps N]
│                               [--codec h265] [--crf N]
│                               [--start T] [--end T]
│
├── batch <glob|dir> -o <output_dir> --preset ID [--workers N]
│
├── presets
│   ├── ls                    # 列出所有预设（内置 + 用户）
│   ├── show <id>             # 显示预设详情
│   └── validate <file.json>  # 校验自定义预设文件
│
├── models
│   ├── ls                    # 列出本地已下载模型
│   ├── available             # 列出所有可下载模型
│   ├── download <key>        # 下载指定模型
│   └── remove <key>          # 删除本地模型
│
└── bench [--preset ID] [--input FILE]  # 性能基准测试
```

#### `enhance` 命令流程

```
解析参数
    → 加载预设（或从 CLI flags 构建内联预设）
    → 选择 / 初始化 InferenceBackend
    → ModelManager.ensure_all(preset.required_models)
    → VideoDecoder(input)
    → Pipeline.from_preset(preset, backend)
    → VideoEncoder(output, ...)
    → Pipeline.run(decoder, encoder)  ← Rich 进度条实时更新
    → 打印耗时 / 速度 / 文件大小对比
```

---

## 4. 核心数据模型

```python
# hipixel_core/models/types.py

@dataclass
class VideoFrame:
    data: np.ndarray          # shape: (H, W, 3), dtype: uint8 或 float32
    pts: float                # presentation timestamp（秒）
    width: int
    height: int
    colorspace: ColorSpace    # BT601 / BT709 / BT2020
    is_hdr: bool = False
    hdr_metadata: dict | None = None  # SMPTE ST 2086 / CEA-861.3

@dataclass
class VideoMeta:
    width: int
    height: int
    fps: float                # 平均帧率
    duration_sec: float
    total_frames: int
    codec: str                # "h264", "h265", "vp9"...
    container: str            # "mp4", "mkv", "mov"...
    colorspace: ColorSpace
    is_hdr: bool
    audio_tracks: list[AudioTrack]
    subtitle_tracks: list[SubtitleTrack]
    bit_depth: int            # 8 / 10 / 12

@dataclass
class DeviceInfo:
    backend_name: str         # "coreml", "cuda"...
    device_name: str          # "Apple M2 Max", "NVIDIA RTX 4090"...
    total_vram_mb: int
    available_vram_mb: int
    driver_version: str | None

@dataclass
class ProgressEvent:
    stage: Literal["setup", "inference", "encode", "done", "error"]
    current_frame: int
    total_frames: int
    fps: float                # 当前处理帧率
    elapsed_sec: float
    eta_sec: float
    gpu_utilization: float    # 0.0-1.0
    gpu_vram_used_mb: int

@dataclass
class PipelineResult:
    success: bool
    output_path: str
    duration_sec: float
    input_meta: VideoMeta
    output_meta: VideoMeta
    avg_fps: float
    peak_vram_mb: int
    error: str | None = None

@dataclass
class OutputSpec:
    resolution: str | tuple[int, int]  # "2x", "4K", (3840, 2160)
    fps: float | Literal["preserve"]
    codec: str
    crf: int | None
    bitrate_kbps: int | None
    container: str
    audio: str
    subtitle: str
    hdr_mode: str
```

---

## 5. 关键流程

### 5.1 单文件增强流程

```
用户：hipixel-core enhance dvdrip.avi --preset old-film-revival -o enhanced.mp4

┌─────────────────────────────────────────────────────────────────────┐
│ 1. 参数解析                                                          │
│    CLI → PresetManager.get("old-film-revival") → Preset             │
│    → BackendSelector.select_backend() → CoreMLBackend               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│ 2. 模型准备                                                          │
│    ModelManager.ensure_all(["NAFNet-REDS-width64",                  │
│                              "RealESRGAN_x2plus"])                   │
│    → 本地存在 + SHA256 校验 ✓                                        │
│    → CoreML 转换缓存（首次运行需 ~30s）                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│ 3. Pipeline.setup()                                                  │
│    → 显存检查：NAFNet(1.2GB) + RealESRGAN(2.1GB) < available(18GB) ✓│
│    → filter.setup() × 3（加载模型、预热）                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│ 4. 主循环（Pipeline.run）                                            │
│                                                                     │
│   VideoDecoder.frames()                                             │
│       │                                                             │
│       ▼ VideoFrame(YUV420)                                          │
│   yuv_to_rgb()                                                      │
│       │                                                             │
│       ▼ VideoFrame(RGB uint8)                                       │
│   NAFNetFilter.process_frame()   ← ONNX 推理（CoreML backend）      │
│       │                                                             │
│       ▼ VideoFrame(RGB uint8, 降噪后)                               │
│   RealESRGANFilter.process_frame()  ← tile 切分 → 推理 → 拼接      │
│       │                                                             │
│       ▼ VideoFrame(RGB uint8, 2x 分辨率)                            │
│   CASFilter.process_frame()      ← GPU shader（无需 ONNX）         │
│       │                                                             │
│       ▼ VideoFrame(最终帧)                                          │
│   rgb_to_yuv()                                                      │
│       │                                                             │
│       ▼                                                             │
│   VideoEncoder.write_frame()                                        │
│       │                                                             │
│   ProgressCallback(frame=N, fps=12.3, eta=32min, gpu_util=94%)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│ 5. 收尾                                                              │
│    VideoEncoder.finalize()                                          │
│    Pipeline.teardown()（释放显存）                                   │
│    打印：输入 720p 30fps → 输出 1440p 30fps，耗时 28min，速度 0.36× │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 显存不足降级流程

```
Pipeline.setup() 发现显存不足
    → 自动减小 tile_size（512 → 256 → 128）
    → 若仍不足，尝试顺序执行（不同时加载所有模型）
    → 若仍不足，提示用户并建议使用 CPU 模式或降低分辨率
    → 写入警告日志，继续（而非崩溃）
```

### 5.3 模型下载流程

```
ModelManager.ensure("RealESRGAN_x2plus")
    → 检查 ~/.hipixel/models/RealESRGAN_x2plus.onnx 是否存在
    → 若存在：SHA256 校验
        → 通过：返回路径
        → 失败：重新下载（文件损坏）
    → 若不存在：
        → 从 models.registry.json 查找下载 URL
        → 分片下载 + 进度回调
        → 完成后 SHA256 校验
        → 写入 models.lock.json
        → 若平台为 macOS：异步触发 CoreML 转换并缓存
```

---

## 6. 性能设计

### 6.1 Tile 切分（超分模型关键优化）

大分辨率帧无法整帧送入 GPU（显存不足），需要切 tile：

```
原始帧 1920×1080
    │
    ▼ tile_size=512, padding=32
┌───────────────────────────────────────┐
│ 实际处理区域（含 padding 重叠部分）   │
│  tile[0,0]: (0,0)→(544,544)          │
│  tile[0,1]: (480,0)→(1024,544)       │
│  ...（步长 = tile_size - 2*padding） │
└───────────────────────────────────────┘
    │
    ▼ 推理后裁剪 padding，拼接
输出帧 3840×2160（×2 超分）
```

`tile_size` 根据可用显存动态调整：

| 可用显存 | tile_size |
|---|---|
| ≥ 10GB | 1024 |
| 4-10GB | 512 |
| 2-4GB | 256 |
| < 2GB | 128（慢，但可运行） |

### 6.2 帧缓冲与流水线并行

```
Decode Thread:   [D1][D2][D3][D4]...
Infer Thread:        [I1][I2][I3]...     ← 与解码重叠
Encode Thread:           [E1][E2]...     ← 与推理重叠

缓冲队列大小：
  decode_queue: maxsize=4（防止解码跑太快吃内存）
  encode_queue: maxsize=4
```

### 6.3 共享 Tensor（多滤镜串联时减少拷贝）

```
目标：NAFNet → RealESRGAN 之间不做 GPU→CPU→GPU 拷贝

方案（Python 阶段）：
  在同一 ONNX Runtime session 中串联 → 复用 IOBinding
  若无法串联（不同模型）：GPU→CPU 一次，CPU→GPU 一次（不可避免）

Phase 2.5 Rust 阶段：
  使用共享 CUDA / Metal 纹理，零拷贝串联
```

---

## 7. 跨平台策略

### 7.1 当前（Phase 0）：Python 优先

| 层 | 实现 |
|---|---|
| CLI | Typer（Python） |
| Pipeline 编排 | Python |
| 视频 I/O | `ffmpeg-python`（subprocess 封装） |
| AI 推理 | ONNX Runtime Python API |
| GPU 后端 | Python Protocol + 各平台 ONNX EP |
| 模型管理 | Python |

### 7.2 Phase 2.5：Rust 内核迁移

迁移策略：**接口不变，实现换掉**。Python 层对上层（CLI / Server Worker）完全透明。

| 层 | Phase 0（Python） | Phase 2.5（Rust 内核） |
|---|---|---|
| 视频解码/编码 | `ffmpeg-python` subprocess | `ffmpeg-sys-next` Rust 绑定 |
| 帧格式转换 | `numpy` | Rust（SIMD 优化） |
| GPU dispatch | ONNX Runtime Python API | `ort` crate（Rust ONNX Runtime 绑定） |
| Python 接口 | 原生 Python | PyO3 暴露 Rust 函数 |
| Swift 接口 | 不存在 | UniFFI 生成 `.swift` 绑定 |

迁移优先级（性能瓶颈优先）：
1. 帧格式转换（YUV/RGB，纯 CPU，Rust SIMD 可得 5-10× 提升）
2. 视频解码（FFmpeg subprocess → 原生绑定，去掉进程间通信开销）
3. GPU dispatch（减少 Python GIL 持有时间）

### 7.3 平台适配矩阵

| 功能 | macOS 14+ | Linux | Windows |
|---|---|---|---|
| CoreML/MPS 后端 | ✅ | ❌ | ❌ |
| CUDA 后端 | ❌ | ✅ | ✅ |
| DirectML 后端 | ❌ | ❌ | ✅（Phase 4） |
| OpenVINO 后端 | ✅ | ✅ | ✅ |
| CPU 兜底 | ✅ | ✅ | ✅ |
| VideoToolbox 硬解 | ✅ | ❌ | ❌ |
| NVDEC 硬解 | ❌ | ✅ | ✅ |

---

## 8. 错误处理

### 错误分类

| 类型 | 示例 | 处理策略 |
|---|---|---|
| `ModelNotFoundError` | 模型文件不存在且无网络 | 提示用户手动下载，给出 URL |
| `InsufficientVRAMError` | 显存不足以运行预设 | 自动降 tile_size，若仍不足则提示 |
| `VideoDecodeError` | 损坏帧 / 不支持格式 | 跳过损坏帧（记录帧号），不中断任务 |
| `InferenceError` | ONNX 推理失败 | 记录失败帧，尝试 CPU 兜底重跑 |
| `DiskSpaceError` | 输出磁盘空间不足 | 任务开始前预检，提前报错 |
| `BackendInitError` | CoreML / CUDA 初始化失败 | 自动降级到下一个可用后端 |

### 进度与错误回传（为 HiPixel Server 设计）

```python
class ProgressEvent:
    stage: str
    current_frame: int
    total_frames: int
    fps: float
    eta_sec: float
    gpu_utilization: float
    error: EnhanceError | None      # 非致命错误（跳帧等）
    fatal: bool = False             # True 时任务终止
```

---

## 9. 测试策略

### 9.1 单元测试

| 测试目标 | 方法 | 断言 |
|---|---|---|
| 各 GPU 后端初始化 | Mock GPU 检测 | 正确选择 backend |
| 帧格式转换 | 固定输入 numpy 数组 | RGB↔YUV 往返误差 < 1 |
| 预设加载 | 加载所有内置 JSON | 无 ValidationError |
| Pipeline.chain | 2 个 Mock Filter | 执行顺序、输出尺寸正确 |
| Tile 切分 / 拼接 | 固定分辨率测试帧 | 边界无缝、无伪影 |

### 9.2 集成测试（CI 运行）

```
测试素材（存于 tests/fixtures/，50MB 以内）：
  - sample_480p_dvdrip.mp4    （10 秒，H.264）
  - sample_720p_anime.mp4     （10 秒，H.264）
  - sample_1080p_live.mp4     （10 秒，H.265）

对每段素材运行每个内置预设，断言：
  - 退出码为 0
  - 输出文件存在且可播放
  - 输出分辨率符合预设定义
```

### 9.3 质量基准（PSNR/SSIM）

```
黄金参考：用 RTX A100 + FP32 跑出的输出作为参考帧

断言：
  - CoreML 后端 PSNR 与参考差值 ≤ 0.5 dB
  - CUDA FP16 PSNR 与参考差值 ≤ 0.5 dB
  - CPU 后端 PSNR 与参考差值 ≤ 0.1 dB（精度最高，速度最慢）
```

### 9.4 性能基准（`hipixel-core bench`）

输出标准化报告：

```
hipixel-core bench --preset old-film-revival --input sample_1080p.mp4

Platform:  Apple M2 Max (30-core GPU)
Backend:   CoreML (MPS)
Available VRAM: 18432 MB

Preset: old-film-revival
  NAFNet (denoise):      8.3 fps  →  2.4 GB VRAM
  RealESRGAN x2:         3.1 fps  →  5.8 GB VRAM
  CAS (sharpen):        82.0 fps  →  0.3 GB VRAM
  Pipeline total:        2.8 fps  →  5.8 GB VRAM peak

Estimated time for 10min @ 1080p 24fps:
  Total frames: 14400
  At 2.8 fps:  ~86 min
```

---

## 10. Phase 2.5 Rust 迁移路径

迁移时，对上层调用者（CLI / HiPixel Server / HiVideo Swift）**接口零变更**。

### 目录结构变化

```
hipixel-core/
├── Cargo.toml             ← 新增：Rust workspace
├── pyproject.toml         ← 保留：CLI 和 Python 层
├── src/                   ← 新增：Rust 内核
│   ├── lib.rs
│   ├── video/
│   │   ├── decoder.rs     ← 替换 hipixel_core/video/decoder.py
│   │   └── encoder.rs     ← 替换 hipixel_core/video/encoder.py
│   ├── backends/
│   │   ├── mod.rs
│   │   ├── coreml.rs      ← 替换 backends/coreml.py
│   │   └── cuda.rs        ← 替换 backends/cuda.py
│   ├── frame.rs           ← 替换 numpy 帧格式转换
│   └── bindings/
│       ├── python.rs      ← PyO3：暴露给 Python 层
│       └── swift.udl      ← UniFFI：生成 Swift binding
└── hipixel_core/
    ├── cli.py             ← 保留（Typer CLI）
    ├── pipeline.py        ← 保留（但调用 Rust 内核）
    └── _core.so           ← PyO3 编译产物（maturin build）
```

### Swift 绑定接口（UniFFI，供 HiVideo Phase 3 使用）

```swift
// 由 UniFFI 自动生成
class HipixelPipeline {
    init(preset: String, backendHint: String?) throws
    func processFrame(frame: VideoFrameData) throws -> VideoFrameData
    func teardown()
}

struct VideoFrameData {
    var data: Data         // RGB bytes
    var width: UInt32
    var height: UInt32
    var pts: Double
}
```

---

> **文档维护**：每个 Phase 结束后更新一次。实现与设计有出入时，以实现为准，更新本文档，并在 Git commit 中注明。
