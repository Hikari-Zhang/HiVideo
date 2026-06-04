// Colors.swift — HiVideo Design Tokens
// Phase 0.5 · SwiftUI 配色 Token
// 对应文档：docs/design/00-tokens.md §1

import SwiftUI

// MARK: - Surface Colors

extension Color {

    // MARK: Background
    /// 窗口/全局背景
    static var surfaceBackground: Color {
        Color("surface.background", bundle: nil)
    }
    /// 卡片/面板主要背景
    static var surfacePrimary: Color {
        Color("surface.primary", bundle: nil)
    }
    /// Hover 态背景、二级卡片
    static var surfaceSecondary: Color {
        Color("surface.secondary", bundle: nil)
    }
    /// 弹窗/浮层
    static var surfaceElevated: Color {
        Color("surface.elevated", bundle: nil)
    }

    // MARK: Text
    /// 主要文字
    static var textPrimary: Color {
        Color.primary
    }
    /// 次要文字、描述
    static var textSecondary: Color {
        Color.secondary
    }
    /// 占位符、禁用文字
    static var textTertiary: Color {
        Color(NSColor.tertiaryLabelColor)
    }
    /// 删除/危险操作
    static var textDestructive: Color {
        Color.red
    }

    // MARK: Border
    /// 卡片描边、分割线
    static var borderDefault: Color {
        Color.primary.opacity(0.10)
    }
    /// 强调描边
    static var borderStrong: Color {
        Color.primary.opacity(0.20)
    }

    // MARK: State
    /// 悬停叠层
    static var stateHover: Color {
        Color.primary.opacity(0.08)
    }
    /// 按下叠层
    static var statePressed: Color {
        Color.primary.opacity(0.15)
    }

    // MARK: Functional
    static var functionalSuccess: Color { Color.green }
    static var functionalWarning: Color { Color.orange }
    static var functionalError:   Color { Color.red }
    static var functionalInfo:    Color { Color.blue }

    // MARK: Character Initials Palette (6 colors, index by characterId % 6)
    static let characterPalette: [Color] = [
        Color.purple,   // 0
        Color.blue,     // 1
        Color.pink,     // 2
        Color.green,    // 3
        Color.orange,   // 4
        Color.teal,     // 5
    ]

    /// 根据角色 ID 返回对应 initials 背景色
    static func characterColor(for id: Int) -> Color {
        characterPalette[abs(id) % characterPalette.count]
    }

    // MARK: HiPixel Brand (Web)
    /// HiPixel Web 主色（紫）
    static var hipixelPurple: Color {
        Color(red: 0.749, green: 0.353, blue: 0.949)
    }
}

// MARK: - Semantic Color Environment Key

struct SurfaceColorKey: EnvironmentKey {
    static let defaultValue: Color = .surfacePrimary
}

extension EnvironmentValues {
    var surfaceColor: Color {
        get { self[SurfaceColorKey.self] }
        set { self[SurfaceColorKey.self] = newValue }
    }
}
