# HiVideo · Phase 0.5 设计交付清单

> 设计→工程对照表。状态：✅ 已有文档/代码 · 🎨 待 Figma 高保真稿 · ❌ 未开始

---

## 交付物总览

| 文件 | 内容 | 状态 |
|------|------|------|
| `docs/design/00-tokens.md` | 配色/字体/间距/圆角/动效完整规范 | ✅ |
| `docs/design/01-hivideo-core.md` | HiVideo 11 个核心界面规范 | ✅ |
| `docs/design/02-hivideo-interactions.md` | HiVideo 9 个高频交互规范 | ✅ |
| `docs/design/03-hipixel-web.md` | HiPixel Web + Windows 5 个界面规范 | ✅ |
| `hipixel-app/HiVideoDesign/Tokens/Colors.swift` | SwiftUI 配色 Token | ✅ |
| `hipixel-app/HiVideoDesign/Tokens/Typography.swift` | SwiftUI 字体 Token | ✅ |
| `hipixel-app/HiVideoDesign/Tokens/Spacing.swift` | SwiftUI 间距/圆角/动效 Token | ✅ |
| `hipixel-app/HiVideoDesign/Components/PosterCard.swift` | 海报卡组件 | ✅ |
| `hipixel-app/HiVideoDesign/Components/CommandPalette.swift` | ⌘K 命令面板组件 | ✅ |
| `hipixel-app/HiVideoDesign/Components/PlayerControls.swift` | 播放器控制条组件 | ✅ |
| `hipixel-app/HiVideoDesign/Components/CharacterCard.swift` | 角色卡 + 详情 Hero 组件 | ✅ |
| Figma 高保真设计稿 | 所有界面的像素级视觉稿 | 🎨 待设计师跟进 |

---

## 界面覆盖对照表

### HiVideo 核心界面

| 界面 | 规范文档 | SwiftUI 组件 | Figma 稿 | Phase |
|------|---------|-------------|---------|-------|
| 启动屏 | `01 §1` | — | 🎨 | Phase 1 Week 4 |
| 主窗口框架 | `01 §2` | `Spacing.swift` (Layout) | 🎨 | Phase 1 Week 1 |
| 媒体库·网格 | `01 §3` | `PosterCard.swift` | 🎨 | Phase 1 Week 5 |
| 媒体库·列表 | `01 §4` | — | 🎨 | Phase 1 Week 5 |
| 媒体库·时间线 | `01 §5` | — | 🎨 | Phase 1 Week 5 |
| 视频详情面板 | `01 §6` | — | 🎨 | Phase 1 Week 5 |
| 播放器 | `01 §7` | `PlayerControls.swift` | 🎨 | Phase 1 Week 2-3 |
| ⌘K 命令面板 | `01 §8` | `CommandPalette.swift` | 🎨 | Phase 1 Week 6 |
| ⌘/ 快捷键速查 | `01 §9` | — | 🎨 | Phase 1 Week 6 |
| 角色侧边栏+主区 | `01 §10` | `CharacterCard.swift` | 🎨 | Phase 5 |
| 角色详情页 | `01 §11` | `CharacterCard.swift` (Header) | 🎨 | Phase 5 |

### HiVideo 高频交互

| 交互 | 规范文档 | SwiftUI 组件 | Figma 稿 | Phase |
|------|---------|-------------|---------|-------|
| 副本选择弹窗 | `02 §1` | — | 🎨 | Phase 7 |
| 删除安全网 Toast | `02 §2` | — | 🎨 | Phase 1 Week 6 |
| 画质增强浮窗 | `02 §3` | — | 🎨 | Phase 3 |
| 音频增强浮窗 | `02 §4` | — | 🎨 | Phase 3 |
| 算力节点设置 | `02 §5` | — | 🎨 | Phase 8 |
| SMB 网盘向导 | `02 §6` | — | 🎨 | Phase 7 |
| 字幕编辑器 | `02 §7` | — | 🎨 | Phase 6 |
| 角色命名弹窗 | `02 §8` | — | 🎨 | Phase 5 |
| 误聚类拆分 | `02 §9` | — | 🎨 | Phase 5 |

### HiPixel Web

| 界面 | 规范文档 | 前端组件 | Figma 稿 | Phase |
|------|---------|---------|---------|-------|
| 上传屏 | `03 §1` | — | 🎨 | Phase 2 |
| 队列屏 | `03 §2` | — | 🎨 | Phase 2 |
| 对比屏 | `03 §3` | — | 🎨 | Phase 2 |
| Windows 安装向导 | `03 §4` | — | 🎨 | Phase 4 |
| Windows 托盘菜单 | `03 §5` | — | 🎨 | Phase 4 |

---

## DEV-PLAN Phase 0.5 完成状态

### 0.5.1 设计基础设施

| 任务 | 状态 | 说明 |
|------|------|------|
| 选定设计工具 | ✅ | Figma（推荐），工程端用 SwiftUI |
| 创建文件结构 | ✅ | `docs/design/` 目录已建立 |
| Apple UI Kit | 🎨 | Figma 工作区建立时引入 |
| SF Symbols 图标库 | ✅ | 映射表见 `00-tokens.md §7` |
| Figma Tokens 插件 | 🎨 | Token JSON 导出见下方 |
| 版本管理规范 | ✅ | 通过 git 追踪 `docs/design/` |

### 0.5.2 Design Token

| Token 类型 | 文档 | Swift 实现 | JSON 导出 |
|-----------|------|-----------|---------|
| 配色（深色/浅色） | ✅ `00 §1` | ✅ `Colors.swift` | 🎨 |
| 字体 | ✅ `00 §2` | ✅ `Typography.swift` | 🎨 |
| 间距 | ✅ `00 §3` | ✅ `Spacing.swift` | 🎨 |
| 圆角 | ✅ `00 §4` | ✅ `Spacing.swift` | 🎨 |
| 阴影/模糊 | ✅ `00 §5` | ✅ `Spacing.swift` | 🎨 |
| 动效 | ✅ `00 §6` | ✅ `Spacing.swift` | 🎨 |
| 基础组件 | ✅（规范文档）| 🔨 Phase 1 实现 | 🎨 |

### 0.5.3 HiVideo 核心界面

| 界面 | 规范 | Figma 高保真 |
|------|------|------------|
| 启动屏 | ✅ | 🎨 |
| 主窗口框架 | ✅ | 🎨 |
| 媒体库网格 | ✅ | 🎨 |
| 媒体库列表 | ✅ | 🎨 |
| 媒体库时间线 | ✅ | 🎨 |
| 视频详情面板 | ✅ | 🎨 |
| 播放器 | ✅ | 🎨 |
| ⌘K 命令面板 | ✅ | 🎨 |
| ⌘/ 快捷键速查 | ✅ | 🎨 |
| 角色侧边栏+主区 | ✅（含工作日志原型） | 🎨 |
| 角色详情页 | ✅（含工作日志原型） | 🎨 |

### 0.5.4 HiVideo 高频交互 — 全部 ✅ 规范完成，🎨 Figma 稿待补

### 0.5.5 HiPixel Web — 全部 ✅ 规范完成，🎨 Figma 稿待补

### 0.5.6 Windows HiPixel — 全部 ✅ 规范完成，🎨 Figma 稿待补

---

## Figma Token JSON（供设计师导入）

```json
{
  "color": {
    "surface": {
      "background": { "dark": "#0A0A0A", "light": "#F2F2F7" },
      "primary":    { "dark": "#1C1C1E", "light": "#FFFFFF" },
      "secondary":  { "dark": "#252528", "light": "#F2F2F7" },
      "elevated":   { "dark": "#2C2C2E", "light": "#FFFFFF" }
    },
    "text": {
      "primary":     { "dark": "#FFFFFF",   "light": "#000000" },
      "secondary":   { "dark": "rgba(235,235,245,0.60)", "light": "rgba(60,60,67,0.60)" },
      "tertiary":    { "dark": "rgba(235,235,245,0.30)", "light": "rgba(60,60,67,0.30)" },
      "destructive": { "dark": "#FF453A",   "light": "#FF3B30" }
    },
    "functional": {
      "success": { "dark": "#30D158", "light": "#34C759" },
      "warning": { "dark": "#FFD60A", "light": "#FF9F0A" },
      "error":   { "dark": "#FF453A", "light": "#FF3B30" },
      "info":    { "dark": "#64D2FF", "light": "#007AFF" }
    },
    "hipixel": {
      "primary": { "light": "#7C3AED", "dark": "#8B5CF6" }
    }
  },
  "spacing": {
    "xxs": "4",  "xs": "8",   "sm": "12",  "md": "16",
    "lg": "20",  "xl": "24",  "xxl": "32", "xxxl": "48"
  },
  "radius": {
    "sm": "6",  "md": "8",  "lg": "12",  "xl": "18",  "full": "9999"
  },
  "animation": {
    "default": { "type": "spring", "response": "0.35", "damping": "0.80" },
    "quick":   { "type": "spring", "response": "0.20", "damping": "0.85" },
    "modal":   { "type": "spring", "response": "0.45", "damping": "0.75" }
  }
}
```

---

## 待 Figma 设计师完成的工作

按优先级排序：

### 🔴 P0（Phase 1 直接需要）
1. 主窗口框架（三栏布局）高保真稿
2. 媒体库·网格视图
3. 播放器（含控制条）
4. 启动屏

### 🟡 P1（Phase 1 后半段）
5. 视频详情面板（含 4 个 Tab）
6. ⌘K 命令面板
7. 媒体库·列表视图
8. 删除安全网 Toast

### 🟢 P2（后续 Phase 启动前完成）
9. 角色系统界面（Phase 5 前）
10. HiPixel Web 三屏（Phase 2 前）
11. 其余高频交互弹窗

---

## 使用方式

1. **工程师**：直接使用 `hipixel-app/HiVideoDesign/` 下的 Swift Token 和组件
2. **设计师**：以 `docs/design/` 文档为规范依据，在 Figma 中创建高保真稿
3. **评审时**：对照本文档核查 Figma 稿是否符合规范（颜色/字体/间距/圆角均有精确数值）

---

*Last updated: 2026-06-04 · Phase 0.5 Handoff v1.0*
