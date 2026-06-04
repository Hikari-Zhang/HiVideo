# HiVideo · Design Tokens

> 设计系统的单一真相来源（Single Source of Truth）。  
> 所有颜色、字体、间距、圆角、动效均从此文档派生。  
> SwiftUI 实现见 `hipixel-app/HiVideoDesign/Tokens/`。

---

## 1. 配色系统

### 1.1 设计原则

- **深色优先**：所有颜色在深色模式下设计，浅色模式为适配
- **语义命名**：不使用 `gray800`，使用 `surface.primary`
- **系统融合**：主色跟随 macOS Accent Color（用户可自定义），无固定品牌色

### 1.2 语义色层级

```
Background 层（最深）
  └─ surface.background    窗口/全局背景
       └─ surface.primary  卡片/面板主要背景
            └─ surface.secondary  卡片悬停/次级背景
                 └─ surface.elevated  浮层/弹窗背景
```

### 1.3 完整 Token 表

#### 背景（Background）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `surface.background` | `#0A0A0A` | `#F2F2F7` | 主窗口背景 |
| `surface.primary` | `#1C1C1E` | `#FFFFFF` | 卡片/面板默认背景 |
| `surface.secondary` | `#252528` | `#F2F2F7` | hover 态背景、二级卡片 |
| `surface.elevated` | `#2C2C2E` | `#FFFFFF` | 弹窗/浮层 |
| `surface.overlay` | `#000000 @ 60%` | `#000000 @ 30%` | 遮罩层 |

#### 文字（Text）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `text.primary` | `#FFFFFF` | `#000000` | 主要文字 |
| `text.secondary` | `#EBEBF5 @ 60%` | `#3C3C43 @ 60%` | 次要文字、描述 |
| `text.tertiary` | `#EBEBF5 @ 30%` | `#3C3C43 @ 30%` | 占位符、禁用文字 |
| `text.link` | `system.accent` | `system.accent` | 可点击链接 |
| `text.destructive` | `#FF453A` | `#FF3B30` | 删除/危险操作文字 |

#### 边框（Border）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `border.default` | `#FFFFFF @ 10%` | `#000000 @ 10%` | 卡片描边、分割线 |
| `border.strong` | `#FFFFFF @ 20%` | `#000000 @ 20%` | 强调描边 |
| `border.focus` | `system.accent` | `system.accent` | 键盘焦点环 |

#### 状态（State）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `state.hover` | `#FFFFFF @ 8%` | `#000000 @ 5%` | 悬停叠层 |
| `state.pressed` | `#FFFFFF @ 15%` | `#000000 @ 10%` | 按下叠层 |
| `state.selected` | `system.accent @ 20%` | `system.accent @ 15%` | 选中背景 |
| `state.disabled` | `#FFFFFF @ 25%` | `#000000 @ 25%` | 禁用态不透明度目标 |

#### 功能色（Functional）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `functional.success` | `#30D158` | `#34C759` | 在线/成功/完成 |
| `functional.warning` | `#FFD60A` | `#FF9F0A` | 警告/等待 |
| `functional.error` | `#FF453A` | `#FF3B30` | 错误/失败/离线 |
| `functional.info` | `#64D2FF` | `#007AFF` | 提示/信息 |
| `functional.purple` | `#BF5AF2` | `#AF52DE` | 角色 initials、HiPixel 主色 |
| `functional.blue` | `#0A84FF` | `#007AFF` | 角色 initials、链接 |
| `functional.pink` | `#FF375F` | `#FF2D55` | 角色 initials |
| `functional.green` | `#30D158` | `#34C759` | 角色 initials |
| `functional.orange` | `#FF9F0A` | `#FF9500` | 角色 initials |
| `functional.teal` | `#5AC8FA` | `#5AC8FA` | 角色 initials |

#### 角色 Initials 色盘（固定 6 色）

角色头像背景色按角色 ID 哈希取模 6：

```
0 → functional.purple  (#BF5AF2 dark)
1 → functional.blue    (#0A84FF dark)
2 → functional.pink    (#FF375F dark)
3 → functional.green   (#30D158 dark)
4 → functional.orange  (#FF9F0A dark)
5 → functional.teal    (#5AC8FA dark)
```

### 1.4 NSVisualEffectView 材质映射

| 使用场景 | Material | Swift API |
|---------|---------|-----------|
| 侧边栏背景 | `.sidebar` | `NSVisualEffectView(material: .sidebar)` |
| 播放控制条 | `.hudWindow` | `NSVisualEffectView(material: .hudWindow)` |
| 弹窗/浮窗背景 | `.popover` | `NSVisualEffectView(material: .popover)` |
| 命令面板 | `.menu` | `NSVisualEffectView(material: .menu)` |
| 工具栏 | `.titlebar` | `NSVisualEffectView(material: .titlebar)` |

---

## 2. 字体系统

### 2.1 字体家族

| 家族 | 用途 |
|------|------|
| **SF Pro Display** | 标题、Hero 文字（≥ 20pt） |
| **SF Pro Text** | 正文、UI 标签（< 20pt） |
| **SF Pro Rounded** | 数字（计数器、时间码、进度百分比） |
| **SF Mono** | 时间戳、路径、代码片段 |

> 均使用系统字体，不引入额外字体文件。

### 2.2 Type Scale

| Token | Size | Weight | Line Height | Tracking | 用途 |
|-------|------|--------|-------------|---------|------|
| `type.largeTitle` | 34pt | Regular | 41pt | +0.37pt | 页面大标题（启动屏） |
| `type.title1` | 28pt | Regular | 34pt | +0.36pt | 侧边栏分组标题 |
| `type.title2` | 22pt | Regular | 28pt | +0.35pt | 卡片标题 |
| `type.title3` | 20pt | Regular | 25pt | +0.38pt | 浮窗标题 |
| `type.headline` | 17pt | **Semibold** | 22pt | -0.41pt | 强调标签 |
| `type.body` | 17pt | Regular | 22pt | -0.41pt | 正文、描述 |
| `type.callout` | 16pt | Regular | 21pt | -0.32pt | 次级正文 |
| `type.subheadline` | 15pt | Regular | 20pt | -0.23pt | 列表副标题 |
| `type.footnote` | 13pt | Regular | 18pt | -0.08pt | 元数据、说明 |
| `type.caption1` | 12pt | Regular | 16pt | 0pt | 时间码、路径 |
| `type.caption2` | 11pt | Regular | 13pt | +0.07pt | 最小徽章文字 |

### 2.3 数字字体（SF Pro Rounded）

```swift
// 时间码专用
Font.system(size: 13, weight: .medium, design: .rounded)
// 进度/计数器
Font.system(size: 15, weight: .semibold, design: .rounded)
```

---

## 3. 间距系统

### 3.1 间距 Token

| Token | Value | 用途 |
|-------|-------|------|
| `spacing.xxs` | 4px | 图标与文字间距、徽章内边距 |
| `spacing.xs` | 8px | 小组件内边距 |
| `spacing.sm` | 12px | 列表行垂直内边距 |
| `spacing.md` | 16px | 标准内边距（卡片/面板） |
| `spacing.lg` | 20px | 大段内边距 |
| `spacing.xl` | 24px | 区块间距 |
| `spacing.xxl` | 32px | 大块间距 |
| `spacing.xxxl` | 48px | 页面边距、大留白 |

### 3.2 组件内边距规范

| 组件 | 水平内边距 | 垂直内边距 |
|------|----------|----------|
| 按钮（标准） | 16px | 8px |
| 按钮（小） | 12px | 6px |
| 卡片 | 16px | 16px |
| 弹窗 | 24px | 20px |
| 侧边栏行 | 12px | 6px |
| 列表行 | 16px | 10px |

### 3.3 布局栅格

```
主窗口三栏：
  侧边栏       主内容区          详情面板
  240px    ← flex →         320px（可收起）
  min:180  min:400          min:280

播放器（沉浸式）：
  0px 边框，铺满窗口
  控制条高度: 72px（含内边距）
  控制条底部偏移: 16px（安全区）
```

---

## 4. 圆角系统

| Token | Value | 用途 |
|-------|-------|------|
| `radius.sm` | 6px | 小按钮、输入框、徽章 |
| `radius.md` | 8px | 标准按钮、列表行选中态 |
| `radius.lg` | 12px | 卡片（海报卡、角色卡） |
| `radius.xl` | 18px | 主窗口圆角、大弹窗 |
| `radius.full` | 9999px | 圆形头像、标签胶囊 |

---

## 5. 阴影系统

| Token | 参数 | 用途 |
|-------|------|------|
| `shadow.sm` | `x:0 y:1 blur:3 color:#000@20%` | 轻微浮起（按钮 hover） |
| `shadow.md` | `x:0 y:4 blur:16 color:#000@30%` | 卡片悬停、小浮窗 |
| `shadow.lg` | `x:0 y:8 blur:32 color:#000@40%` | 弹窗、命令面板 |
| `shadow.overlay` | `x:0 y:16 blur:64 color:#000@60%` | 全屏遮罩背后主窗口 |

---

## 6. 动效系统

### 6.1 Spring 参数（标准）

| Token | Response | Damping | 用途 |
|-------|----------|---------|------|
| `animation.default` | 0.35s | 0.80 | 常规交互（按钮、选中） |
| `animation.quick` | 0.20s | 0.85 | Toast、徽章出现 |
| `animation.modal` | 0.45s | 0.75 | 弹窗弹入 |
| `animation.panel` | 0.40s | 0.80 | 详情面板滑入 |

### 6.2 使用规则

```swift
// 标准 spring
.animation(.spring(response: 0.35, dampingFraction: 0.80), value: isSelected)

// 弹窗弹入
.animation(.spring(response: 0.45, dampingFraction: 0.75), value: isPresented)
```

### 6.3 过渡规范

| 场景 | 过渡方式 |
|------|---------|
| 侧边栏收起/展开 | `.slide` + spring |
| 详情面板滑入 | `.move(edge: .trailing)` + spring |
| Toast 出现 | `.move(edge: .top)` + opacity |
| 命令面板 | `.scale(0.95)` + opacity |
| 弹窗 | `.scale(0.96)` + opacity |
| 卡片 hover | scale(1.02) + shadow 增强 |

---

## 7. 图标规范

### 7.1 SF Symbols 使用原则

- 优先使用系统 SF Symbols，不引入自定义 icon 文件
- 尺寸与 type scale 对齐（body → 17pt symbol）
- 权重与文字权重匹配（semibold 文字配 semibold symbol）

### 7.2 核心图标映射

| 功能 | SF Symbol | 备注 |
|------|-----------|------|
| 播放 | `play.fill` | |
| 暂停 | `pause.fill` | |
| 全屏进入 | `arrow.up.left.and.arrow.down.right` | |
| 全屏退出 | `arrow.down.right.and.arrow.up.left` | |
| 音量 | `speaker.wave.2.fill` | 根据音量级别切换 |
| 静音 | `speaker.slash.fill` | |
| 字幕 | `captions.bubble.fill` | |
| 音轨 | `waveform` | |
| 画质增强 | `sparkles` | ✨ 启用时填充 |
| 画中画 | `pip.enter` | |
| 命令面板 | `magnifyingglass` | ⌘K |
| 快捷键 | `keyboard` | ⌘/ |
| 媒体库 | `rectangle.grid.2x2.fill` | |
| 列表视图 | `list.bullet` | |
| 时间线 | `timeline.selection` | |
| 角色 | `person.2.fill` | |
| 标签 | `tag.fill` | |
| 网盘 | `externaldrive.fill.badge.wifi` | |
| 节点 | `server.rack` | |
| 字幕编辑 | `text.bubble.fill` | |
| 添加 | `plus` | |
| 删除 | `trash.fill` | |
| 设置 | `gearshape.fill` | |

---

*Last updated: 2026-06-04 · Phase 0.5 Design Tokens v1.0*
