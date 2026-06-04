// Spacing.swift — HiVideo Design Tokens
// Phase 0.5 · SwiftUI 间距/圆角/阴影/动效 Token
// 对应文档：docs/design/00-tokens.md §3-6

import SwiftUI

// MARK: - Spacing

enum Spacing {
    /// 4pt — 图标与文字间距、徽章内边距
    static let xxs: CGFloat = 4
    /// 8pt — 小组件内边距
    static let xs:  CGFloat = 8
    /// 12pt — 列表行垂直内边距
    static let sm:  CGFloat = 12
    /// 16pt — 标准内边距（卡片/面板）
    static let md:  CGFloat = 16
    /// 20pt — 大段内边距
    static let lg:  CGFloat = 20
    /// 24pt — 区块间距
    static let xl:  CGFloat = 24
    /// 32pt — 大块间距
    static let xxl: CGFloat = 32
    /// 48pt — 页面边距、大留白
    static let xxxl: CGFloat = 48
}

// MARK: - Corner Radius

enum Radius {
    /// 6pt — 小按钮、输入框、徽章
    static let sm:   CGFloat = 6
    /// 8pt — 标准按钮、列表行选中态
    static let md:   CGFloat = 8
    /// 12pt — 卡片（海报卡、角色卡）
    static let lg:   CGFloat = 12
    /// 18pt — 主窗口圆角、大弹窗
    static let xl:   CGFloat = 18
    /// 9999pt — 圆形头像、标签胶囊
    static let full: CGFloat = 9999
}

// MARK: - Shadow

struct HiVShadow {
    let color: Color
    let radius: CGFloat
    let x: CGFloat
    let y: CGFloat
}

enum Shadow {
    /// 轻微浮起（按钮 hover）
    static let sm = HiVShadow(color: .black.opacity(0.20), radius: 3, x: 0, y: 1)
    /// 卡片悬停、小浮窗
    static let md = HiVShadow(color: .black.opacity(0.30), radius: 16, x: 0, y: 4)
    /// 弹窗、命令面板
    static let lg = HiVShadow(color: .black.opacity(0.40), radius: 32, x: 0, y: 8)
    /// 全屏遮罩背后主窗口
    static let overlay = HiVShadow(color: .black.opacity(0.60), radius: 64, x: 0, y: 16)
}

extension View {
    func hivShadow(_ s: HiVShadow) -> some View {
        shadow(color: s.color, radius: s.radius, x: s.x, y: s.y)
    }
}

// MARK: - Animation

enum HiVAnimation {
    /// 常规交互（按钮、选中）
    static let `default` = Animation.spring(response: 0.35, dampingFraction: 0.80)
    /// Toast、徽章出现
    static let quick     = Animation.spring(response: 0.20, dampingFraction: 0.85)
    /// 弹窗弹入
    static let modal     = Animation.spring(response: 0.45, dampingFraction: 0.75)
    /// 详情面板滑入
    static let panel     = Animation.spring(response: 0.40, dampingFraction: 0.80)
}

// MARK: - Layout Constants

enum Layout {
    // 主窗口
    static let sidebarWidth:      CGFloat = 240
    static let sidebarMinWidth:   CGFloat = 180
    static let detailPanelWidth:  CGFloat = 320
    static let detailPanelMin:    CGFloat = 280

    // 播放器
    static let controlBarHeight:  CGFloat = 72
    static let controlBarBottom:  CGFloat = 16

    // 海报卡（网格视图基础尺寸）
    static let posterWidth:       CGFloat = 160
    static let posterHeight:      CGFloat = 240

    // 角色头像
    static let characterAvatarLg: CGFloat = 96   // 详情页 Hero
    static let characterAvatarMd: CGFloat = 56   // 列表/网格
    static let characterAvatarSm: CGFloat = 32   // 侧边栏

    // 命令面板
    static let commandPaletteMaxWidth:  CGFloat = 640
    static let commandPaletteMaxHeight: CGFloat = 480
}

// MARK: - Visual Effect View (NSVisualEffectView Bridge)

#if os(macOS)
import AppKit

struct VisualEffectView: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode

    init(_ material: NSVisualEffectView.Material,
         blendingMode: NSVisualEffectView.BlendingMode = .behindWindow) {
        self.material = material
        self.blendingMode = blendingMode
    }

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }

    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}

// 常用材质快捷方式
extension VisualEffectView {
    /// 侧边栏背景
    static var sidebar: VisualEffectView {
        VisualEffectView(.sidebar, blendingMode: .behindWindow)
    }
    /// 播放控制条（HUD 风格）
    static var hud: VisualEffectView {
        VisualEffectView(.hudWindow, blendingMode: .withinWindow)
    }
    /// 弹窗/浮窗
    static var popover: VisualEffectView {
        VisualEffectView(.popover, blendingMode: .withinWindow)
    }
    /// 命令面板
    static var menu: VisualEffectView {
        VisualEffectView(.menu, blendingMode: .behindWindow)
    }
}
#endif
